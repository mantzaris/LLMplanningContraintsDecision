#!/usr/bin/env python3
"""Export compact schedule-free analysis tables and trace pointers from actual runs."""

from pathlib import Path
import argparse
import shutil
from plancheck.budget import Journal
from plancheck.util import digest, file_hash, immutable_json, read_json


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--analysis", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    for name in ("summary.json", "metrics.json", "selector-diagnostics.json", "provenance.json"):
        immutable_json(args.output / name, read_json(args.analysis / name))
    if not (args.output / "metrics.csv").exists():
        shutil.copyfile(args.analysis / "metrics.csv", args.output / "metrics.csv")
    traces = read_json(args.analysis / "representative-traces.json")
    compact = {}
    for category, trace in traces.items():
        compact[category] = {k: trace[k] for k in ("scenario_id", "replicate", "request")}
        compact[category]["candidates"] = [
            {
                "candidate_id": c["candidate_id"],
                "formula": c["formula"],
                "aliases": c["aliases"],
                "plan": c["plan"],
                "acceptance_count": sum(c["signature"]),
                "acceptance_hash": digest(c["signature"]),
            }
            for c in trace["bundle"]["candidates"]
        ]
        compact[category]["translation_errors"] = trace["bundle"]["errors"]
        compact[category]["outputs"] = {
            method: {
                budget: {
                    k: o.get(k)
                    for k in (
                        "status",
                        "semantic_status",
                        "plan_id",
                        "initial_plan_id",
                        "final_formula",
                        "events",
                        "errors",
                        "witnesses",
                        "judgments",
                        "repairs",
                    )
                }
                for budget, o in prefixes.items()
            }
            for method, prefixes in trace["outputs"].items()
        }
    immutable_json(args.output / "representative-traces.json", compact)
    identities = {}
    for path in sorted(args.run.rglob("*")):
        if path.is_file() and path.suffix in {".json", ".jsonl"}:
            identities[str(path.relative_to(args.run))] = {
                "sha256": file_hash(path),
                "bytes": path.stat().st_size,
            }
    immutable_json(
        args.output / "full-artifact-manifest.json",
        {
            "run_identity": args.run.name,
            "mode": read_json(args.run / "manifest.json")["mode"],
            "files": identities,
            "local_storage": str(args.run),
            "remote_replication": "pending: gateway cannot reach pod",
            "no_new_generations": not any(
                e["event"] == "generation_start" and not e.get("copied_for_replay")
                for e in Journal(args.run / "calls.jsonl").read()
            ),
        },
    )
    immutable_json(args.output / "run-manifest.json", read_json(args.run / "manifest.json"))
    print(f"Exported {len(identities)} raw-artifact identities and compact results")


if __name__ == "__main__":
    main()
