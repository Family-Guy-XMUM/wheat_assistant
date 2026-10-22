"""Coordinator regressions for stop ownership, port evidence and partial receipts."""
import importlib.util
import json
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

from maizi.process_control import ManagedProcess
from maizi.release_evidence import report_path, write_report

ROOT = Path(__file__).resolve().parents[1]


def load_script(name):
    spec = importlib.util.spec_from_file_location('maizi_test_'+name, ROOT/'scripts'/f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize('ignore_signal', [False, True])
def test_owned_tree_shutdown_and_forced_cleanup_are_distinguished(tmp_path, ignore_signal):
    script = tmp_path/'synthetic_process.py'
    script.write_text('''import pathlib, signal, subprocess, sys, time
ignore=sys.argv[1]=='ignore'
handler=signal.SIG_IGN if ignore else lambda *args: sys.exit(0)
for name in ('SIGTERM','SIGBREAK'):
    if hasattr(signal,name): signal.signal(getattr(signal,name),handler)
if len(sys.argv)==3:
    child=subprocess.Popen([sys.executable,__file__,sys.argv[1],sys.argv[2]+'.child','child'])
    pathlib.Path(sys.argv[2]).write_text(str(child.pid))
else:
    pathlib.Path(sys.argv[2]).write_text('ready')
while True: time.sleep(.05)
''')
    ready = tmp_path/'ready.txt'
    managed = ManagedProcess([sys.executable,str(script),'ignore' if ignore_signal else 'normal',str(ready)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        deadline = time.monotonic()+10
        while not ready.exists() and time.monotonic()<deadline:
            assert managed.process.poll() is None
            time.sleep(.02)
        assert ready.exists()
        # Both the parent and its child are positively identified as owned.
        child_pid = int(ready.read_text())
        deadline = time.monotonic()+5
        while child_pid not in [p.pid for p in managed.family()] and time.monotonic()<deadline:
            time.sleep(.02)
        assert child_pid in managed.members
        child_ready = Path(str(ready)+'.child')
        deadline = time.monotonic()+5
        while not child_ready.exists() and time.monotonic()<deadline:
            time.sleep(.02)
        assert child_ready.exists()
        evidence = managed.stop(grace_seconds=.25 if ignore_signal else 5)
        assert evidence['remaining_processes'] == 0
        assert evidence['children_observed'] >= 1
        assert evidence['forced_cleanup'] is ignore_signal
        assert evidence['graceful'] is (not ignore_signal)
    finally:
        managed.stop(grace_seconds=0)


def test_access_denied_is_never_evidence_of_a_released_port(monkeypatch):
    verify = load_script('verify_release')
    class DeniedSocket:
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def settimeout(self,*args): pass
        def connect_ex(self,*args): return 10013
    monkeypatch.setattr(verify.socket,'socket',lambda:DeniedSocket())
    with pytest.raises(RuntimeError,match='denied'):
        verify.released_port(8765)


def test_partial_benchmark_never_calculates_an_acceptance_median(monkeypatch):
    benchmark = load_script('benchmark_release')
    monkeypatch.setattr(benchmark,'candidate_info',lambda root:{'version':'0.2.1','ai_calls':0})
    monkeypatch.setattr(benchmark,'trial',lambda:{'complete':False,'status':'failed','phase':'temporary_directory_cleanup','winerror':32,'export_seconds':1.0,'cleanup_passed':False})
    result = benchmark.benchmark()
    assert result['passed'] is False
    assert result['export_median_seconds'] is None
    assert result['complete_trials'] == 0
    assert [x['status'] for x in result['runs']] == ['failed','not_run','not_run']
    assert result['runs'][0]['winerror'] == 32


def test_new_attempt_preserves_an_existing_failed_receipt(tmp_path):
    original = tmp_path/'performance.json'
    write_report(original,{'passed':False,'phase':'original_windows_failure'})
    target = report_path(tmp_path,'performance.json',original)
    assert target != original
    write_report(target,{'passed':True})
    assert json.loads(original.read_text()) == {'passed':False,'phase':'original_windows_failure'}
    assert not list(tmp_path.glob('*.tmp'))


@pytest.mark.parametrize('exit_before_stop', [False, True])
def test_unexpected_exit_is_never_a_graceful_stop(tmp_path, exit_before_stop):
    ready = tmp_path/'ready'
    code = '''import pathlib, signal, sys, time
def fail(*args): raise SystemExit(3)
for name in ('SIGTERM','SIGBREAK'):
    if hasattr(signal,name): signal.signal(getattr(signal,name),fail)
pathlib.Path(sys.argv[1]).write_text('ready')
if sys.argv[2]=='early': raise SystemExit(3)
while True: time.sleep(.02)
'''
    managed = ManagedProcess([sys.executable,'-c',code,str(ready),'early' if exit_before_stop else 'signal'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        deadline = time.monotonic()+10
        while not ready.exists() and time.monotonic()<deadline:
            time.sleep(.02)
        assert ready.exists()
        if exit_before_stop:
            managed.process.wait(timeout=5)
        evidence = managed.stop(grace_seconds=5)
        assert evidence['graceful'] is False
        assert evidence['exit_code'] == 3
        assert evidence['expected_exit_code'] is False
        assert evidence['forced_cleanup'] is False
        assert evidence['remaining_processes'] == 0
    finally:
        managed.stop(grace_seconds=0)
