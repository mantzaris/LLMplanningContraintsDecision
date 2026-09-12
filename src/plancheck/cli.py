"""Configuration-driven Stage 1 commands."""

from __future__ import annotations
import argparse
import json
import subprocess
from pathlib import Path
from .util import immutable_json, read_json


def main():
    parser = argparse.ArgumentParser(prog="plancheck")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("acquire", "prepare", "smoke"):
        command = commands.add_parser(name)
        command.add_argument("--config", type=Path, required=True)
        if name == "acquire":
            command.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
        elif name == "prepare":
            command.add_argument("--feed", type=Path, required=True)
            command.add_argument("--output", type=Path, default=Path("data/prepared"))
        else:
            command.add_argument("--public", type=Path, default=Path("data/prepared/public"))
            command.add_argument("--run", type=Path, required=True)
            command.add_argument("--model-path", required=True)
            command.add_argument("--cache-from", type=Path)
    commands.add_parser("cpu-check")
    probe = commands.add_parser("gpu-diagnostic")
    probe.add_argument("--output", type=Path, required=True)
    replay = commands.add_parser("replay")
    replay.add_argument("--run", type=Path, required=True)
    replay.add_argument("--output", type=Path, required=True)
    evaluate = commands.add_parser("evaluate")
    evaluate.add_argument("--run", type=Path, required=True)
    evaluate.add_argument("--references", type=Path, required=True)
    report = commands.add_parser("report")
    report.add_argument("--run", type=Path, required=True)
    report.add_argument("--output", type=Path, required=True)
    export = commands.add_parser("export-audit")
    export.add_argument("--run", type=Path, required=True)
    export.add_argument("--output", type=Path, required=True)
    for name in (
        "pilot-prepare",
        "pilot-review",
        "pilot-freeze",
        "pilot-run",
        "pilot-replay",
        "pilot-analyze",
        "pilot-history",
        "pilot-figures",
    ):
        command = commands.add_parser(name)
        if name in {"pilot-prepare", "pilot-freeze", "pilot-run"}:
            command.add_argument("--config", type=Path, required=True)
        if name == "pilot-prepare":
            command.add_argument("--feed", type=Path, required=True)
            command.add_argument("--prior-public", type=Path, required=True)
        if name == "pilot-freeze":
            command.add_argument("--prepared", type=Path, required=True)
        if name in {"pilot-review", "pilot-run", "pilot-analyze"}:
            command.add_argument("--public", type=Path, required=True)
        if name in {"pilot-review", "pilot-analyze"}:
            command.add_argument("--references", type=Path, required=True)
        if name in {"pilot-run", "pilot-replay", "pilot-analyze", "pilot-history"}:
            command.add_argument("--run", type=Path, required=True)
        if name == "pilot-run":
            command.add_argument("--model-path", required=True)
        else:
            command.add_argument("--output", type=Path, required=True)
        if name == "pilot-figures":
            command.add_argument("--analysis", type=Path, required=True)
            command.add_argument("--label", required=True)
    args = parser.parse_args()
    if args.command == "pilot-prepare":
        from .pilot_data import prepare_pilot

        result = prepare_pilot(args.feed, read_json(args.config), args.prior_public, args.output)
    elif args.command == "pilot-review":
        from .pilot_review import review_collection

        result = review_collection(args.public, args.references, args.output)
    elif args.command == "pilot-freeze":
        from .pilot_protocol import freeze

        result = freeze(read_json(args.config), args.prepared, args.output)
    elif args.command == "pilot-run":
        from .pilot import run_pilot

        result = run_pilot(
            read_json(args.config), args.public, args.run, model_path=args.model_path
        )
    elif args.command == "pilot-replay":
        from .pilot import replay_pilot

        result = replay_pilot(args.run, args.output)
    elif args.command == "pilot-analyze":
        from .pilot_analysis import analyze_pairs

        result = analyze_pairs(args.run, args.public, args.references, args.output)
    elif args.command == "pilot-history":
        from .pilot_history import reanalyze_history

        result = reanalyze_history(args.run, args.output)
    elif args.command == "pilot-figures":
        from .pilot_figures import figures

        result = figures(args.analysis, args.output, args.label)
    elif args.command == "acquire":
        from .gtfs import acquire

        result = str(
            acquire(args.raw_dir, Path("data/manifests"), read_json(args.config)["source"])
        )
    elif args.command == "prepare":
        from .prepare import prepare

        result = prepare(args.feed, read_json(args.config), args.output)
    elif args.command == "cpu-check":
        import sys

        raise SystemExit(subprocess.call([sys.executable, "-m", "pytest", "-q"]))
    elif args.command == "gpu-diagnostic":
        from .model import gpu_probe

        result = gpu_probe()
        immutable_json(args.output, result)
    elif args.command == "smoke":
        from .runner import run

        result = run(
            read_json(args.config),
            args.public,
            args.run,
            args.model_path,
            cache_from=args.cache_from,
        )
    elif args.command == "replay":
        from .runner import replay

        result = replay(args.run, args.output)
    elif args.command == "evaluate":
        from .evaluation import evaluate_run

        result = evaluate_run(args.run, args.references)
    elif args.command == "report":
        from .evaluation import report

        print(report(args.run, args.output))
        return
    elif args.command == "export-audit":
        from .audit import export_audit

        result = export_audit(args.run, args.output)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
