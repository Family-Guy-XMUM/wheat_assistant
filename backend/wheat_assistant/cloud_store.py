"""Bounded, browser-scoped SQL storage. Local SQLite remains in store.py."""
from __future__ import annotations

import hashlib
import json
import re
import threading
import uuid
from contextlib import nullcontext
from contextvars import ContextVar
from pathlib import Path

from sqlalchemy import Column, Integer, JSON, LargeBinary, String, create_engine, select, update
from sqlalchemy.engine import make_url
from sqlalchemy.orm import declarative_base, sessionmaker

from wheat_assistant.store import now

workspace_context = ContextVar("wheat_workspace", default=None)
Base = declarative_base()


class Workspace(Base):
    __tablename__ = "wheat_workspaces"
    id = Column(String(64), primary_key=True)
    used_bytes = Column(Integer, nullable=False, default=0)
    entity_count = Column(Integer, nullable=False, default=0)
    created = Column(String, nullable=False)


class Entity(Base):
    __tablename__ = "wheat_cloud_entities"
    workspace = Column(String(64), primary_key=True)
    id = Column(String(32), primary_key=True)
    kind = Column(String, nullable=False, index=True)
    payload = Column(JSON, nullable=False)
    revision = Column(Integer, nullable=False, default=1)
    created = Column(String, nullable=False)


class Blob(Base):
    __tablename__ = "wheat_cloud_blobs"
    workspace = Column(String(64), primary_key=True)
    name = Column(String, primary_key=True)
    content = Column(LargeBinary, nullable=False)
    checksum = Column(String(64), nullable=False)


class DailyBudget(Base):
    __tablename__ = "wheat_cloud_model_budget"
    day = Column(String(10), primary_key=True)
    calls = Column(Integer, nullable=False, default=0)


def size(payload):
    return len(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode())


class CloudDatabase:
    def __init__(self, url, root, *, engine=None, max_workspaces=100, max_bytes=67108864, daily_calls=20):
        if engine is None:
            parsed = make_url(url or "")
            if parsed.get_backend_name() not in {"postgresql", "postgres"}:
                raise ValueError("Replit cloud mode requires a PostgreSQL DATABASE_URL")
            engine = create_engine(parsed.set(drivername="postgresql+psycopg"),
                                   pool_pre_ping=True, pool_recycle=300, pool_size=5, max_overflow=5,
                                   connect_args={"connect_timeout": 10}, hide_parameters=True)
        self.engine = engine
        self.Session = sessionmaker(bind=engine)
        self.cache_root = Path(root)
        self.max_workspaces, self.max_bytes = max_workspaces, max_bytes
        self._locks = {}
        self._lock = threading.Lock()
        self.usage_lock = threading.Lock()
        self.daily_calls = daily_calls
        Base.metadata.create_all(engine)

    def close(self):
        self.engine.dispose()

    def exists(self, identifier):
        with self.Session() as session:
            return session.get(Workspace, identifier) is not None

    def new_workspace(self, identifier):
        with self._lock, self.Session.begin() as session:
            if len(session.scalars(select(Workspace.id).limit(self.max_workspaces)).all()) >= self.max_workspaces:
                raise ValueError("All demo workspaces are in use. Please try again later.")
            session.add(Workspace(id=identifier, created=now(), used_bytes=0, entity_count=0))

    def scope(self, identifier):
        if not identifier or not re.fullmatch(r"[a-f0-9]{64}", identifier):
            raise RuntimeError("A verified browser workspace is required")
        with self._lock:
            lock = self._locks.setdefault(identifier, threading.Lock())
        return CloudStore(self, identifier, lock)

    def __getattr__(self, name):
        # ContextVars are copied into FastAPI's sync worker threads.
        return getattr(self.scope(workspace_context.get()), name)

    def recover(self):
        # Replit must run one VM and one app worker. Recover before serving traffic.
        with self.Session.begin() as session:
            for row in session.scalars(select(Entity).where(Entity.kind.in_(["run", "export"]))):
                payload = dict(row.payload)
                changed = False
                if row.kind == "run" and payload.get("status") == "running":
                    payload.update(status="interrupted", error="The app restarted. Retry this immutable run.")
                    changed = True
                if row.kind == "run" and payload.get("export_state") == "building":
                    payload.update(export_state="interrupted", export_error="The app restarted during export. Retry export.")
                    changed = True
                if row.kind == "export" and payload.get("status") == "building":
                    payload.update(status="interrupted", error="Export interrupted by restart")
                    changed = True
                if changed:
                    row.payload, row.revision = payload, row.revision + 1


class CloudStore:
    def __init__(self, database, workspace, lock):
        self.database, self.workspace, self.lock = database, workspace, lock
        self.root = database.cache_root / workspace
        for folder in ("files", "artifacts"):
            (self.root / folder).mkdir(parents=True, exist_ok=True)

    def _row(self, session, kind, identifier):
        row = session.get(Entity, (self.workspace, identifier))
        if row is None or row.kind != kind:
            raise KeyError(identifier)
        return row

    def _quota(self, session, delta=0, added=0):
        row = session.get(Workspace, self.workspace, with_for_update=True)
        if row is None:
            raise KeyError(self.workspace)
        if row.used_bytes + delta > self.database.max_bytes or row.entity_count + added > 1500:
            raise ValueError("This demo workspace reached its storage limit. Reuse the existing synthetic files.")
        row.used_bytes += delta
        row.entity_count += added

    def add(self, kind, data):
        return self.commit_bundle(additions=[(kind, data)])[0]

    def get(self, kind, identifier):
        with self.database.Session() as session:
            return dict(self._row(session, kind, identifier).payload)

    def list(self, kind):
        with self.database.Session() as session:
            rows = session.scalars(select(Entity).where(Entity.workspace == self.workspace, Entity.kind == kind)
                                   .order_by(Entity.created.desc(), Entity.id.desc()))
            return [dict(row.payload) for row in rows]

    def put(self, kind, identifier, data):
        self.commit_bundle(updates=[(kind, identifier, data)])
        return self.get(kind, identifier)

    def activity(self, action, subject, detail):
        return self.add("activity", {"action": action, "subject": subject, "detail": detail})

    def commit_bundle(self, updates=(), additions=()):
        created = []
        # Every provider attempt, including a JSON repair, creates one usage record.
        # The same transaction reserves its application-wide daily slot first.
        guard = self.database.usage_lock if any(kind == "usage" for kind, _ in additions) else nullcontext()
        with guard, self.database.Session.begin() as session:
            self._quota(session)  # Serialize a workspace transaction at the database too.
            delta = 0
            for kind, identifier, data in updates:
                row = self._row(session, kind, identifier)
                payload = {**data, "id": identifier, "created_at": row.created}
                delta += size(payload) - size(row.payload)
                revision = row.revision
                result = session.execute(update(Entity).where(Entity.workspace == self.workspace,
                    Entity.id == identifier, Entity.revision == revision).values(payload=payload, revision=revision + 1))
                if result.rowcount != 1:
                    raise ValueError("Concurrent update; reload the run")
            for kind, data in additions:
                if kind == "usage":
                    budget = session.get(DailyBudget, now()[:10], with_for_update=True)
                    if budget is None:
                        budget = DailyBudget(day=now()[:10], calls=0)
                        session.add(budget)
                    if budget.calls >= self.database.daily_calls:
                        raise ValueError("The shared demo's daily AI-call limit has been reached. Use the editable setup.")
                    budget.calls += 1
                payload = {**data, "id": data.get("id") or uuid.uuid4().hex, "created_at": now()}
                delta += size(payload)
                session.add(Entity(workspace=self.workspace, id=payload["id"], kind=kind,
                                   payload=payload, created=payload["created_at"], revision=1))
                created.append(payload)
            self._quota(session, delta, len(created))
        return created

    def _path(self, folder, name):
        if folder not in {"files", "artifacts"} or Path(name).name != name or not name or name in {".", ".."}:
            raise ValueError("Invalid stored file name")
        return self.root / folder / name

    def write_blob(self, folder, name, content):
        path = self._path(folder, name)
        key = folder + "/" + name
        checksum = hashlib.sha256(content).hexdigest()
        with self.database.Session.begin() as session:
            self._quota(session)
            previous = session.get(Blob, (self.workspace, key))
            if previous is None:
                self._quota(session, len(content))
                session.add(Blob(workspace=self.workspace, name=key, content=content, checksum=checksum))
            elif previous.checksum != checksum:
                raise ValueError("An immutable stored file cannot be replaced")
        if not path.exists():
            temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
            temporary.write_bytes(content)
            temporary.chmod(0o400)
            temporary.replace(path)
        return path

    def blob_path(self, folder, name):
        path = self._path(folder, name)
        if not path.is_file():
            with self.database.Session() as session:
                row = session.get(Blob, (self.workspace, folder + "/" + name))
                if row is None:
                    return path
                content, checksum = bytes(row.content), row.checksum
            if hashlib.sha256(content).hexdigest() != checksum:
                raise ValueError("The stored file failed its integrity check")
            temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
            temporary.write_bytes(content)
            temporary.chmod(0o400)
            temporary.replace(path)
        return path

    def persist_artifact(self, name):
        path = self._path("artifacts", name)
        self.write_blob("artifacts", name, path.read_bytes())
        return path
