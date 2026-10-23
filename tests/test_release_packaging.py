"""A source ZIP must describe its exact bytes and reject concurrent changes."""
import hashlib
import importlib.util
import json
import sys
import zipfile
from pathlib import Path

import pytest
from wheat_assistant.release_evidence import manifest_digest


def package_module(tmp_path, monkeypatch):
    script = Path(__file__).resolve().parents[1]/'scripts/package_source.py'
    spec = importlib.util.spec_from_file_location('wheat_assistant_package_test',script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module,'ROOT',tmp_path)
    (tmp_path/'README.md').write_text('Synthetic packaging fixture\n')
    backend = tmp_path/'backend/wheat_assistant'
    backend.mkdir(parents=True)
    (backend/'__init__.py').write_text('__version__ = "0.2.1"\n')
    return module


def test_package_manifest_and_metadata_describe_exact_archive_bytes(tmp_path, monkeypatch):
    module = package_module(tmp_path,monkeypatch)
    target = tmp_path/'candidate.zip'
    monkeypatch.setattr(sys,'argv',['package_source.py','--output',str(target)])
    module.main()
    with zipfile.ZipFile(target) as archive:
        manifest = json.loads(archive.read('wheat_assistant/SOURCE_MANIFEST.json'))
        info = json.loads(archive.read('wheat_assistant/CANDIDATE.json'))
        assert info['candidate_sha256'] == manifest_digest(manifest)
        assert manifest['README.md'] == hashlib.sha256(archive.read('wheat_assistant/README.md')).hexdigest()
        assert set(manifest) == {'README.md','backend/wheat_assistant/__init__.py'}


@pytest.mark.parametrize('changed_kind', ['source','evidence'])
def test_change_during_packaging_rejects_and_removes_only_own_zip(tmp_path, monkeypatch, changed_kind):
    module = package_module(tmp_path,monkeypatch)
    target = tmp_path/'candidate.zip'
    sentinel = tmp_path/'older-candidate.zip'
    sentinel.write_bytes(b'preserved previous artifact')
    receipts = tmp_path/'receipts'
    receipts.mkdir()
    receipt = receipts/'final-checks.json'
    receipt.write_text(json.dumps({'version':'0.2.1','source_sha256':module.candidate_info(tmp_path)['source_sha256'],'passed':True}))
    original = zipfile.ZipFile.writestr
    changed = False
    def concurrent_write(self, *args, **kwargs):
        nonlocal changed
        result = original(self,*args,**kwargs)
        if not changed:
            changed = True
            if changed_kind == 'source':
                (tmp_path/'README.md').write_text('Changed concurrently\n')
            else:
                receipt.write_text(json.dumps({'version':'0.2.1','passed':False}))
        return result
    monkeypatch.setattr(zipfile.ZipFile,'writestr',concurrent_write)
    monkeypatch.setattr(sys,'argv',['package_source.py','--output',str(target),'--verification-dir',str(receipts)])
    with pytest.raises(SystemExit,match='changed during packaging'):
        module.main()
    assert not target.exists()
    assert sentinel.read_bytes() == b'preserved previous artifact'
