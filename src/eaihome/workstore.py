"""Local-only persistence for explicitly entered fictional work corrections.

SQLite events survive a process restart and an FTS reindex. This is NOT an
authenticated decision service: actor labels are local test assertions.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .continuity import TRANSITIONS, at, load_scenario, work_status
from .store import init

VERSION = 1
GENESIS = "0" * 64
FUTURE = "9999-12-31T23:59:59+00:00"
REQUEST_ID = re.compile(r"^[A-Za-z0-9_-]{6,80}$")
OPERATOR_EVENTS = frozenset({
    "task.accepted", "task.completed", "task.dismissed",
    "commitment.confirmed", "commitment.cancelled",
})


def _canonical(value: dict) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _required(value: str, field: str, limit: int) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError(f"{field}: verplichte tekst van maximaal {limit} tekens")
    return value.strip()


class CorrectionStore:
    """One fixed fictional scenario per private local data folder.

    No remote calls, content edits, identity verification or automatic action.
    """

    def __init__(self, home: Path, scenario_path: Path):
        self.home = home.expanduser().resolve()
        self.scenario_path = scenario_path.expanduser().resolve()
        self.scenario = load_scenario(self.scenario_path, self.scenario_path.parents[2])
        self.scenario_digest = hashlib.sha256(self.scenario_path.read_bytes()).hexdigest()
        self.path = self.home / "work-events.sqlite3"

    def _connect(self, write: bool) -> sqlite3.Connection | None:
        if not write and not self.path.exists():
            return None
        if write:
            init(self.home)
            db = sqlite3.connect(self.path, timeout=10, isolation_level=None)
            if self.path.exists():
                self.path.chmod(0o600)
        else:
            db = sqlite3.connect(f"file:{self.path}?mode=ro", timeout=10, uri=True, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=10000")
        if write:
            db.execute("PRAGMA synchronous=FULL")
        return db

    def _scope(self, db: sqlite3.Connection, create: bool) -> None:
        version = db.execute("PRAGMA user_version").fetchone()[0]
        if version == 0 and create:
            db.execute(
                "CREATE TABLE IF NOT EXISTS scope "
                "(id INTEGER PRIMARY KEY CHECK (id=1), case_id TEXT NOT NULL, "
                "context_id TEXT NOT NULL, scenario_sha256 TEXT NOT NULL)"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS events "
                "(seq INTEGER PRIMARY KEY AUTOINCREMENT, request_id TEXT NOT NULL UNIQUE, "
                "request_sha256 TEXT NOT NULL, payload_json TEXT NOT NULL, "
                "prev_sha256 TEXT NOT NULL, event_sha256 TEXT NOT NULL)"
            )
            db.execute(f"PRAGMA user_version={VERSION}")
        elif version != VERSION:
            raise ValueError("Onbekende versie van het lokale gebeurtenissenregister")
        row = db.execute("SELECT case_id,context_id,scenario_sha256 FROM scope WHERE id=1").fetchone()
        current = (self.scenario["case_id"], self.scenario["context_id"], self.scenario_digest)
        if row is None and create:
            db.execute(
                "INSERT INTO scope (id,case_id,context_id,scenario_sha256) VALUES (1,?,?,?)",
                current,
            )
        elif row is None or tuple(row) != current:
            raise ValueError("Scenario of context is gewijzigd: expliciete migratie nodig")

    def _rows(self, db: sqlite3.Connection) -> list[dict]:
        records = []
        previous = GENESIS
        for row in db.execute(
            "SELECT seq,request_id,request_sha256,payload_json,prev_sha256,event_sha256 "
            "FROM events ORDER BY seq"
        ):
            encoded = row["payload_json"]
            computed = _digest(previous + "\n" + encoded)
            if row["prev_sha256"] != previous or row["event_sha256"] != computed:
                raise ValueError(f"Registerintegriteit ongeldig bij gebeurtenis {row['seq']}")
            try:
                payload = json.loads(encoded)
            except json.JSONDecodeError as exc:
                raise ValueError("Onleesbare gebeurtenis in het register") from exc
            if (
                payload.get("request_id") != row["request_id"]
                or payload.get("context_id") != self.scenario["context_id"]
                or payload.get("case_id") != self.scenario["case_id"]
                or payload.get("scenario_sha256") != self.scenario_digest
                or payload.get("event_kind") not in OPERATOR_EVENTS
                or payload.get("actor_kind") != "person"
                or payload.get("subject_id") not in self.scenario["subjects"]
                or payload.get("id") != "local_" + _digest(row["request_id"])[:24]
            ):
                raise ValueError("Ongeldig event of werkcontext in lokaal register")
            at(payload.get("recorded_at"), "recorded_at")
            at(payload.get("effective_at"), "effective_at")
            kind, _, _, actors = TRANSITIONS[payload["event_kind"]]
            if self.scenario["subjects"][payload["subject_id"]]["kind"] != kind or "person" not in actors:
                raise ValueError("Ongeldig type gebeurtenis in lokaal register")
            payload["_recorded"] = at(payload["recorded_at"], "recorded_at")
            payload["_effective"] = at(payload["effective_at"], "effective_at")
            payload["_anchor"] = {
                "kind": "unverified_local_operator_note",
                "reason": payload["reason"],
                "actor_ref": payload["actor_ref"],
                "local_event_sha256": computed,
            }
            records.append({"payload": payload, "request_id": row["request_id"],
                            "request_sha256": row["request_sha256"], "chain_sha256": computed})
            previous = computed
        return records

    def _combined(self, rows: list[dict]) -> dict:
        return {**self.scenario, "events": [
            *self.scenario["events"], *(row["payload"] for row in rows)
        ]}

    def view(self, known_at: str, effective_at: str | None = None) -> dict:
        db = self._connect(write=False)
        rows: list[dict] = []
        if db is not None:
            try:
                db.execute("BEGIN")
                self._scope(db, create=False)
                rows = self._rows(db)
                db.commit()
            finally:
                db.close()
        result = work_status(self._combined(rows), known_at, effective_at)
        result["local_correction_count"] = len(rows)
        result["store_kind"] = "local_unverified_demo"
        return result

    def append(
        self, *,
        request_id: str,
        subject_id: str,
        event_kind: str,
        actor_ref: str,
        reason: str,
        expected_revision: int,
        effective_at: str | None = None,
        recorded_at: str | None = None,
    ) -> dict:
        """Append one locally declared correction under a SQLite write transaction.

        expected_revision counts *all* baseline and local events for the subject.
        recorded_at is injectable for deterministic tests, not a trusted clock.
        """
        if not isinstance(request_id, str) or not REQUEST_ID.fullmatch(request_id):
            raise ValueError("request_id: gebruik 6-80 letters, cijfers, _ of -")
        if event_kind not in OPERATOR_EVENTS:
            raise ValueError("Deze lokale demo mag alleen beperkte correcties vastleggen")
        if subject_id not in self.scenario["subjects"]:
            raise ValueError("Onbekend werkobject")
        if self.scenario["subjects"][subject_id]["kind"] != TRANSITIONS[event_kind][0]:
            raise ValueError("Gebeurtenis past niet bij werkobject")
        if not isinstance(expected_revision, int) or isinstance(expected_revision, bool) or expected_revision < 0:
            raise ValueError("expected_revision: niet-negatief geheel getal vereist")
        actor = _required(actor_ref, "actor_ref", 100)
        explanation = _required(reason, "reason", 500)
        if len(explanation) < 5:
            raise ValueError("reason: geef een concrete toelichting")
        # Validate before opening the database; only timezone-aware times are accepted.
        if effective_at is not None:
            at(effective_at, "effective_at")
        if recorded_at is not None:
            at(recorded_at, "recorded_at")
        request = {
            "request_id": request_id, "case_id": self.scenario["case_id"],
            "context_id": self.scenario["context_id"], "scenario_sha256": self.scenario_digest,
            "subject_id": subject_id, "event_kind": event_kind,
            "actor_ref": actor, "reason": explanation, "expected_revision": expected_revision,
            "requested_effective_at": effective_at,
        }
        fingerprint = _digest(_canonical(request))
        db = self._connect(write=True)
        assert db is not None
        try:
            # Bootstrap is its own committed transaction. A rejected first
            # correction must not leave a version-0, unreadable empty database.
            db.execute("BEGIN IMMEDIATE")
            self._scope(db, create=True)
            db.commit()
            db.execute("BEGIN IMMEDIATE")
            self._scope(db, create=False)
            rows = self._rows(db)
            for existing in rows:
                if existing["request_id"] == request_id:
                    if existing["request_sha256"] != fingerprint:
                        raise ValueError("Idempotency-sleutel opnieuw gebruikt voor een andere opdracht")
                    db.commit()
                    return {"event_id": existing["payload"]["id"],
                            "revision": existing["payload"]["revision"], "replayed": True,
                            "event_sha256": existing["chain_sha256"]}
            state = work_status(self._combined(rows), FUTURE, FUTURE)
            items = [*state["open_tasks"], *state["proposed_tasks"], *state["other_objects"]]
            subject = next(x for x in items if x["id"] == subject_id)
            revision = len(subject["trace"])
            if revision != expected_revision:
                raise ValueError(f"Verouderde revisie: verwacht {expected_revision}, actueel {revision}")
            timestamp = recorded_at or datetime.now(timezone.utc).isoformat(timespec="microseconds")
            applies = effective_at or timestamp
            payload = {
                **request,
                "id": "local_" + _digest(request_id)[:24],
                "actor_kind": "person",
                "recorded_at": timestamp,
                "effective_at": applies,
                "revision": revision + 1,
            }
            encoded = _canonical(payload)
            previous = rows[-1]["chain_sha256"] if rows else GENESIS
            event_hash = _digest(previous + "\n" + encoded)
            candidate = {
                **payload, "_recorded": at(timestamp, "recorded_at"),
                "_effective": at(applies, "effective_at"),
                "_anchor": {"kind": "unverified_local_operator_note",
                            "reason": explanation, "actor_ref": actor,
                            "local_event_sha256": event_hash},
            }
            # Domain transitions must hold for the complete history, not just latest UI state.
            work_status({
                **self.scenario,
                "events": [*self._combined(rows)["events"], candidate],
            }, FUTURE, FUTURE)
            db.execute(
                "INSERT INTO events "
                "(request_id,request_sha256,payload_json,prev_sha256,event_sha256) VALUES (?,?,?,?,?)",
                (request_id, fingerprint, encoded, previous, event_hash),
            )
            db.commit()
            return {"event_id": payload["id"], "revision": payload["revision"],
                    "replayed": False, "event_sha256": event_hash}
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
