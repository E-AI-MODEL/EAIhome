"""Local CLI. Group labels are filters, not identity proof or enterprise ACL."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from . import __version__
from .continuity import load_scenario, work_status
from .workstore import CorrectionStore
from .search import rebuild, search, versions
from .store import add_file, init, verify


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="eaihome", description="Local-first corpus and source-aware search")
    p.add_argument("--home", type=Path, default=Path(os.environ.get("EAIHOME_HOME", "~/.local/share/eaihome")).expanduser())
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("init", help="Create a private local data folder")
    add = sub.add_parser("add", help="Import a single immutable source")
    add.add_argument("path", type=Path)
    add.add_argument("--family", required=True)
    add.add_argument("--revision", required=True, help="Source revision label, never inferred")
    add.add_argument("--source", default="manual")
    add.add_argument("--group", action="append", default=None, help="Allowed group (repeatable)")
    add.add_argument("--updated", help="Source update time in ISO 8601 with timezone")
    add.add_argument("--occurred", help="Event time in ISO 8601 with timezone")
    add.add_argument("--origin", help="Stable original-source identifier, if known")
    sub.add_parser("index", help="Verify SHA-256 and rebuild SQLite FTS5 index")
    sub.add_parser("verify", help="Check original file integrity")
    lookup = sub.add_parser("search", help="Search all document versions")
    lookup.add_argument("query")
    lookup.add_argument("--group", action="append", default=None)
    lookup.add_argument("--limit", type=int, default=10)
    history = sub.add_parser("versions", help="List all authorised versions of a family")
    history.add_argument("family")
    history.add_argument("--group", action="append", default=None)
    demo = sub.add_parser("work-demo", help="Show a fictional work timeline with source anchors")
    demo.add_argument("--scenario", type=Path,
                      default=Path(__file__).resolve().parents[2] / "fixtures/scenarios/EAIhome_mockup_work_scenario.json")
    demo.add_argument("--known-at", required=True, help="What was known at this timezone-aware instant?")
    demo.add_argument("--effective-at", help="What applied at this instant? Defaults to --known-at")
    corrected = sub.add_parser("work-correct", help="Record a fictional local operator correction")
    corrected.add_argument("--scenario", type=Path,
                           default=Path(__file__).resolve().parents[2] / "fixtures/scenarios/EAIhome_mockup_corrections.json")
    corrected.add_argument("--subject", required=True)
    corrected.add_argument("--event", required=True, help="Example: task.dismissed")
    corrected.add_argument("--actor", required=True, help="Local demo label only, not verified identity")
    corrected.add_argument("--reason", required=True)
    corrected.add_argument("--expected-revision", type=int, required=True)
    corrected.add_argument("--request-id", required=True, help="Retry-safe idempotency key")
    corrected.add_argument("--effective-at", help="Timezone-aware effective time; otherwise recorded time")
    state = sub.add_parser("work-state", help="Reconstruct demo work status plus saved corrections")
    state.add_argument("--scenario", type=Path,
                       default=Path(__file__).resolve().parents[2] / "fixtures/scenarios/EAIhome_mockup_corrections.json")
    state.add_argument("--known-at", required=True)
    state.add_argument("--effective-at")
    canvas = sub.add_parser("work-canvas", help="Build a fictional workspace with a local LLM")
    canvas.add_argument("--port", type=int, default=8765, help="Loopback port (default 8765)")
    canvas.add_argument("--model", default="qwen3:4b", help="Installed Ollama model for layout plans")
    return p


def main(argv: list[str] | None = None) -> int:
    p = parser()
    args = p.parse_args(argv)
    home = args.home.expanduser().resolve()
    group = tuple(args.group or ["owner"]) if hasattr(args, "group") else ("owner",)
    try:
        if args.command == "init":
            init(home)
            result = {"home": str(home), "created": True}
        elif args.command == "add":
            result = add_file(
                home, args.path, family=args.family, version=args.revision,
                source_system=args.source, groups=group,
                source_updated_at=args.updated, occurred_at=args.occurred, origin_id=args.origin,
            )
        elif args.command == "index":
            result = rebuild(home)
        elif args.command == "verify":
            result = verify(home)
        elif args.command == "search":
            result = search(home, args.query, groups=group, limit=args.limit)
        elif args.command == "work-canvas":
            from .live_canvas import serve_canvas
            return serve_canvas(home, model=args.model, port=args.port)
        elif args.command == "work-correct":
            record = CorrectionStore(home, args.scenario)
            result = record.append(
                request_id=args.request_id, subject_id=args.subject,
                event_kind=args.event, actor_ref=args.actor, reason=args.reason,
                expected_revision=args.expected_revision, effective_at=args.effective_at,
            )
        elif args.command == "work-state":
            record = CorrectionStore(home, args.scenario)
            result = record.view(args.known_at, args.effective_at)
        elif args.command == "work-demo":
            scenario_path = args.scenario.expanduser().resolve()
            scenario = load_scenario(scenario_path, scenario_path.parents[2])
            result = work_status(scenario, args.known_at, args.effective_at)
        else:
            result = versions(home, args.family, groups=group)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError) as exc:
        p.exit(2, f"error: {exc}\n")
    return 2
