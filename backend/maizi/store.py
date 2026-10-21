from __future__ import annotations

import hashlib
import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import JSON, Column, Integer, String, create_engine, select, update
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()
class Entity(Base):
    __tablename__ = "entities"
    id = Column(String, primary_key=True)
    kind = Column(String, nullable=False, index=True)
    payload = Column(JSON, nullable=False)
    revision = Column(Integer, default=1, nullable=False)
    created = Column(String, nullable=False)

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str).encode()).hexdigest()

def now():
    return datetime.now(timezone.utc).isoformat()

class Store:
    def __init__(self, root: Path):
        self.root = root
        root.mkdir(parents=True, exist_ok=True)
        (root / "files").mkdir(exist_ok=True)
        (root / "artifacts").mkdir(exist_ok=True)
        self.engine = create_engine("sqlite:///" + str(root / "maizi.sqlite"), connect_args={"check_same_thread": False, "timeout": 30})
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.lock = threading.Lock()

    def add(self, kind, data):
        payload = {**data, "id": uuid.uuid4().hex, "created_at": now()}
        with self.Session.begin() as session:
            session.add(Entity(id=payload["id"], kind=kind, payload=payload, created=payload["created_at"]))
        return payload

    def get(self, kind, identifier):
        with self.Session() as session:
            row = session.get(Entity, identifier)
            if not row or row.kind != kind:
                raise KeyError(identifier)
            return dict(row.payload)

    def list(self, kind):
        with self.Session() as session:
            rows = session.scalars(select(Entity).where(Entity.kind == kind).order_by(Entity.created.desc())).all()
            return [dict(row.payload) for row in rows]

    def put(self, kind, identifier, data):
        with self.Session.begin() as session:
            row = session.get(Entity, identifier)
            if not row or row.kind != kind:
                raise KeyError(identifier)
            revision = row.revision
            result = session.execute(update(Entity).where(Entity.id == identifier, Entity.revision == revision).values(
                payload={**data, "id": identifier, "created_at": row.created}, revision=revision + 1))
            if result.rowcount != 1:
                raise ValueError("Concurrent update; reload the run")
        return self.get(kind, identifier)

    def activity(self, action, subject, detail):
        return self.add("activity", {"action": action, "subject": subject, "detail": detail})
