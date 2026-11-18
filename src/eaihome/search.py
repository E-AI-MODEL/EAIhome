"""Disposable SQLite FTS index, with explicit ACL and all-version retrieval."""

from __future__ import annotations

import json
import os
import re
import sqlite3
from pathlib import Path

from .store import extract, object_path, records, verify

TOKEN = re.compile(r"\w+", re.UNICODE)


def chunks(content: str, maximum: int = 1100) -> list[tuple[str, str]]:
    section = "Document"
    pending: list[str] = []
    out: list[tuple[str, str]] = []

    def flush() -> None:
        if pending:
            combined = "\n".join(pending).strip()
            for start in range(0, len(combined), maximum):
                fragment = combined[start : start + maximum].strip()
                if fragment:
                    out.append((section, fragment))
            pending.clear()

    for line in content.splitlines():
        if line.lstrip().startswith("# ") or line.lstrip().startswith("## ") or line.lstrip().startswith("### "):
            flush()
            section = line.lstrip("# ").strip() or "Document"
        else:
            pending.append(line)
    flush()
    return out


def db_path(home: Path) -> Path:
    return home / "index.sqlite3"


def rebuild(home: Path) -> dict:
    inspection = verify(home)
    if inspection["broken_blobs"]:
        raise ValueError("Source integrity check failed: " + ", ".join(inspection["broken_blobs"]))
    if not home.is_dir():
        raise ValueError("Run init or import a document first")
    temp_db = home / "index.building.sqlite3"
    if temp_db.exists():
        temp_db.unlink()
    conn = sqlite3.connect(temp_db)
    try:
        conn.executescript("""
            PRAGMA foreign_keys = ON;
            CREATE TABLE docs (
                record_id TEXT PRIMARY KEY,
                family_id TEXT NOT NULL,
                version TEXT NOT NULL,
                title TEXT NOT NULL,
                sha256 TEXT NOT NULL,
                source_system TEXT NOT NULL,
                source_updated_at TEXT,
                occurred_at TEXT,
                ingested_at TEXT NOT NULL,
                origin_id TEXT NOT NULL
            );
            CREATE TABLE doc_acl (
                record_id TEXT NOT NULL REFERENCES docs(record_id),
                group_name TEXT NOT NULL,
                PRIMARY KEY (record_id, group_name)
            );
            CREATE TABLE passages (
                id INTEGER PRIMARY KEY,
                record_id TEXT NOT NULL REFERENCES docs(record_id),
                section TEXT NOT NULL,
                content TEXT NOT NULL
            );
            CREATE VIRTUAL TABLE passages_fts USING fts5(content, content='passages', content_rowid='id');
        """)
        passages_total = 0
        for r in records(home):
            if r["ingest_status"] != "processed":
                continue
            raw = object_path(home, r["sha256"]).read_bytes()
            text = extract(raw, Path(r["title"]).suffix.lower())
            if text is None:
                raise ValueError("Extractor changed without a migration")
            conn.execute(
                "INSERT INTO docs VALUES (?,?,?,?,?,?,?,?,?,?)",
                (r["record_id"], r["family_id"], r["version"], r["title"], r["sha256"],
                 r["source_system"], r["source_updated_at"], r["occurred_at"], r["ingested_at"], r["origin_id"]),
            )
            for g in r["allowed_groups"]:
                conn.execute("INSERT INTO doc_acl VALUES (?,?)", (r["record_id"], g))
            for heading, piece in chunks(text):
                cur = conn.execute(
                    "INSERT INTO passages (record_id,section,content) VALUES (?,?,?)",
                    (r["record_id"], heading, piece),
                )
                conn.execute("INSERT INTO passages_fts (rowid,content) VALUES (?,?)", (cur.lastrowid, piece))
                passages_total += 1
        conn.commit()
    except Exception:
        conn.close()
        if temp_db.exists():
            temp_db.unlink()
        raise
    conn.close()
    os.chmod(temp_db, 0o600)
    os.replace(temp_db, db_path(home))
    return {**inspection, "indexed_passages": passages_total}


def _connection(home: Path) -> sqlite3.Connection:
    if not db_path(home).is_file():
        raise ValueError("No index found: run index first")
    conn = sqlite3.connect(f"file:{db_path(home).as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _groups(groups: tuple[str, ...]) -> list[str]:
    valid = sorted({g.strip() for g in groups if g.strip()})
    if not valid:
        raise ValueError("Access group required")
    return valid


def search(home: Path, query: str, *, groups: tuple[str, ...] = ("owner",), limit: int = 10) -> dict:
    if not 1 <= limit <= 50:
        raise ValueError("limit must be between 1 and 50")
    terms = TOKEN.findall(query.casefold())[:24]
    if not terms:
        return {"query": query, "matches": [], "note": "No search terms"}
    fts_query = " OR ".join('"' + term.replace('"', '""') + '"' for term in terms)
    allowed = _groups(groups)
    slots = ",".join("?" for _ in allowed)
    # ACL happens inside SQL, before ranking and limiting. Caller group is not authentication.
    sql = f"""
      SELECT d.record_id,d.family_id,d.version,d.title,d.sha256,d.source_system,
             d.source_updated_at,d.occurred_at,d.origin_id,
             p.section,p.content,bm25(passages_fts) AS relevance
      FROM passages_fts JOIN passages p ON p.id=passages_fts.rowid
      JOIN docs d ON d.record_id=p.record_id
      WHERE passages_fts MATCH ?
        AND EXISTS (SELECT 1 FROM doc_acl a
                    WHERE a.record_id=d.record_id AND a.group_name IN ({slots}))
      ORDER BY relevance ASC LIMIT ?
    """
    conn = _connection(home)
    try:
        rows = conn.execute(sql, [fts_query, *allowed, 2000]).fetchall()
    finally:
        conn.close()
    grouped: dict[tuple[str, str], dict] = {}
    for r in rows:
        # Identical bytes + identical passage are one textual observation,
        # even if several imported files point to that blob.
        key = (r["sha256"], r["content"])
        if key in grouped:
            grouped[key]["also_record_ids"].append(r["record_id"])
            if r["version"] not in grouped[key]["versions"]:
                grouped[key]["versions"].append(r["version"])
            continue
        grouped[key] = {
            "record_id": r["record_id"], "also_record_ids": [], "family_id": r["family_id"],
            "version": r["version"], "versions": [r["version"]], "title": r["title"],
            "sha256": r["sha256"], "source_system": r["source_system"],
            "source_updated_at": r["source_updated_at"], "occurred_at": r["occurred_at"],
            "origin_id": r["origin_id"], "section": r["section"],
            "excerpt": r["content"][:750],
        }
    return {
        "query": query,
        "matches": list(grouped.values())[:limit],
        "note": "A text match is not evidence that a generated assertion has been checked or proven.",
    }


def versions(home: Path, family: str, *, groups: tuple[str, ...] = ("owner",)) -> list[dict]:
    allowed = _groups(groups)
    slots = ",".join("?" for _ in allowed)
    conn = _connection(home)
    try:
        rows = conn.execute(
            f"""SELECT d.record_id,d.family_id,d.version,d.title,d.sha256,
                       d.source_updated_at,d.ingested_at,d.origin_id
                  FROM docs d WHERE d.family_id=?
                  AND EXISTS (SELECT 1 FROM doc_acl a WHERE a.record_id=d.record_id
                              AND a.group_name IN ({slots}))
                  ORDER BY d.ingested_at, d.record_id""",
            [family, *allowed],
        ).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]
