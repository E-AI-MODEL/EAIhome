"""Immutable source blobs and an append-only, inspectable source registry.

No network calls. SQLite is a disposable index, not the source of truth.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import uuid
from datetime import datetime, timezone
from email import policy
from email.parser import BytesParser
from pathlib import Path

SUPPORTED_SUFFIXES = {".md", ".markdown", ".txt", ".csv", ".json", ".eml"}
MAX_BYTES = 12 * 1024 * 1024


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def safe_date(value: str | None) -> str | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("Date must be ISO 8601") from exc
    if parsed.tzinfo is None:
        raise ValueError("Date needs a UTC offset (e.g. +00:00 or Z)")
    return parsed.isoformat()


def private_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if os.name == "posix":
        path.chmod(0o700)


def init(home: Path) -> None:
    private_dir(home)
    private_dir(home / "objects")
    if not (home / "manifest.jsonl").exists():
        fd = os.open(home / "manifest.jsonl", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.close(fd)


def records(home: Path) -> list[dict]:
    manifest = home / "manifest.jsonl"
    if not manifest.exists():
        return []
    found = []
    with manifest.open("r", encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            if not line.strip():
                continue
            try:
                found.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Corrupt registry line {lineno}") from exc
    return found


def object_path(home: Path, digest: str) -> Path:
    if len(digest) != 64 or any(x not in "0123456789abcdef" for x in digest):
        raise ValueError("Invalid SHA-256")
    return home / "objects" / digest[:2] / digest


def extract(data: bytes, suffix: str) -> str | None:
    """Only deterministic, local text extraction. Unsupported formats stay unindexed."""
    if suffix not in SUPPORTED_SUFFIXES:
        return None
    if suffix == ".eml":
        msg = BytesParser(policy=policy.default).parsebytes(data)
        header = [f"Subject: {msg.get('subject', '')}", f"From: {msg.get('from', '')}", f"Date: {msg.get('date', '')}"]
        parts = [msg] if not msg.is_multipart() else msg.walk()
        bodies = []
        for part in parts:
            if part.get_content_type() != "text/plain" or part.get_content_disposition() == "attachment":
                continue
            try:
                bodies.append(part.get_content())
            except (UnicodeError, LookupError, ValueError):
                continue
        return "\n".join(header + bodies)
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("Only UTF-8 files are supported in this version") from exc


def add_file(
    home: Path,
    path: Path,
    *,
    family: str,
    version: str,
    source_system: str = "manual",
    groups: tuple[str, ...] = ("owner",),
    source_updated_at: str | None = None,
    occurred_at: str | None = None,
    origin_id: str | None = None,
) -> dict:
    if not path.is_file():
        raise ValueError("Only regular files can be imported")
    if not family.strip() or not version.strip() or not source_system.strip():
        raise ValueError("Family, version and source system are required")
    unique_groups = sorted({g.strip() for g in groups if g.strip()})
    if not unique_groups:
        raise ValueError("At least one permitted group is required (fail closed)")
    if path.stat().st_size > MAX_BYTES:
        raise ValueError("File exceeds 12 MiB limit")
    data = path.read_bytes()
    if len(data) > MAX_BYTES:
        raise ValueError("File exceeds 12 MiB limit")
    digest = hashlib.sha256(data).hexdigest()
    suffix = path.suffix.lower()
    extracted = extract(data, suffix)
    init(home)
    blob = object_path(home, digest)
    private_dir(blob.parent)
    if not blob.exists():
        with tempfile.NamedTemporaryFile(dir=blob.parent, delete=False) as tmp:
            tmp.write(data)
            tmp.flush()
            os.fsync(tmp.fileno())
            temp_path = Path(tmp.name)
        os.chmod(temp_path, 0o600)
        os.replace(temp_path, blob)
    elif hashlib.sha256(blob.read_bytes()).hexdigest() != digest:
        raise ValueError("Existing source blob does not match its hash")
    previous = next((r for r in records(home) if r["sha256"] == digest), None)
    record = {
        "record_type": "source",
        "schema_version": "0.1",
        "record_id": "src_" + uuid.uuid4().hex,
        "family_id": family.strip(),
        "version": version.strip(),
        "title": path.name,
        "source_system": source_system.strip(),
        "source_updated_at": safe_date(source_updated_at),
        "occurred_at": safe_date(occurred_at),
        "ingested_at": now_utc(),
        "sha256": digest,
        "origin_id": origin_id or "sha256:" + digest,
        "duplicate_of": previous["record_id"] if previous else None,
        "allowed_groups": unique_groups,
        "extractor": "stdlib-v1" if extracted is not None else None,
        "ingest_status": "processed" if extracted is not None else "unsupported_format",
    }
    with (home / "manifest.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        fh.flush()
        os.fsync(fh.fileno())
    return record


def verify(home: Path) -> dict:
    found = records(home)
    checked: set[str] = set()
    errors: list[str] = []
    for r in found:
        digest = r["sha256"]
        if digest in checked:
            continue
        checked.add(digest)
        try:
            blob = object_path(home, digest)
            if not blob.is_file() or hashlib.sha256(blob.read_bytes()).hexdigest() != digest:
                errors.append(digest)
        except (ValueError, OSError):
            errors.append(digest)
    return {"records": len(found), "unique_blobs": len(checked), "broken_blobs": errors}
