"""Publish small run evidence without redistributing agency schedule tables/prompts."""

from __future__ import annotations
from pathlib import Path
from .budget import Journal
from .util import file_hash, immutable_json, read_json


def export_audit(run_dir: Path, destination: Path) -> dict:
    events = Journal(run_dir / "calls.jsonl").read()
    successes = [
        e for e in events if e["event"] == "generation_success" and not e.get("copied_for_replay")
    ]
    starts = [
        e for e in events if e["event"] == "generation_start" and not e.get("copied_for_replay")
    ]
    outputs = [read_json(p) for p in sorted((run_dir / "outputs").glob("*.json"))]
    records = []
    for output in outputs:
        records.append(
            {
                **{
                    k: output.get(k)
                    for k in (
                        "scenario_id",
                        "base_id",
                        "method",
                        "status",
                        "semantic_status",
                        "plan_id",
                        "initial_plan_id",
                        "diagnostic_fallback_plan_id",
                        "events",
                        "method_wall_seconds",
                    )
                },
                "translation_attempts": len(output["translations"]),
                "candidates": [
                    {
                        "id": c["candidate_id"],
                        "aliases": c["aliases"],
                        "plan": c["plan"],
                        "accepted_pool_journeys": sum(c["signature"]),
                    }
                    for c in output["candidates"]
                ],
                "witnesses": output["witnesses"],
                "judgments": [
                    {
                        "journey_id": j["journey_id"],
                        "verdict": j["judgment"]["verdict"],
                        "source_spans": j["judgment"]["spans"],
                    }
                    for j in output["judgments"]
                ],
                "repairs": [{"kind": r["kind"]} for r in output["repairs"]],
                "errors": [
                    {k: e.get(k) for k in ("phase", "status", "index")} for e in output["errors"]
                ],
                "logical_calls": output["logical_calls"],
            }
        )
    result = {
        "label": "development smoke; provisional unaudited annotations",
        "manifest": read_json(run_dir / "manifest.json"),
        "actual_compute": {
            "generation_attempts": len(starts),
            "successful_generations": len(successes),
            "failed_generations": sum(e["event"] == "generation_error" for e in events),
            "input_tokens": sum(e["response"]["input_tokens"] for e in successes),
            "output_tokens": sum(e["response"]["output_tokens"] for e in successes),
            "generation_seconds": sum(e["response"]["latency_seconds"] for e in successes),
            "peak_memory_bytes": max(
                (e["response"].get("peak_memory_bytes", 0) for e in successes), default=0
            ),
            "output_devices": sorted(
                {e["response"].get("output_device", "unknown") for e in successes}
            ),
        },
        "evaluation": read_json(run_dir / "evaluation.json"),
        "outputs": records,
        "saved_artifact_hashes": {
            str(p.relative_to(run_dir)): file_hash(p)
            for p in sorted(run_dir.rglob("*"))
            if p.is_file()
        },
        "gpu_evidence": {p.name: read_json(p) for p in sorted(run_dir.glob("gpu-*.json"))},
    }
    immutable_json(destination, result)
    return result
