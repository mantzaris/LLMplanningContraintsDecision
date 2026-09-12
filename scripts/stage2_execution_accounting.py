#!/usr/bin/env python3
"""Reconstruct Stage 2 and cumulative compute from preserved journals, without inference."""

from __future__ import annotations
import argparse
from collections import Counter
from pathlib import Path
from plancheck.budget import Journal
from plancheck.util import file_hash, immutable_json, read_json


def account(run: Path, ledger: Path, previous: Path) -> dict:
    events = Journal(ledger).read()
    allocations = [e for e in events if e["event"] == "allocation"]
    assert len(allocations) == 1 and allocations[0]["stage"] == "stage2"
    starts = {e["session"]: e for e in events if e["event"] == "session_start"}
    ends = {e["session"]: e for e in events if e["event"] == "session_end"}
    seconds = sum(
        ends[s]["elapsed_seconds"] if s in ends else e["reserved_seconds"]
        for s, e in starts.items()
    )
    attempts = sum(e["event"] == "request_start" for e in events)
    calls = [e for e in Journal(run / "calls.jsonl").read() if not e.get("copied_for_replay")]
    responses = [e["response"] for e in calls if e["event"] == "generation_success"]
    run_attempts = sum(e["event"] == "generation_start" for e in calls)
    # This allocation contains one completed primary run; refuse to hide additional attempts.
    assert attempts == run_attempts and starts.keys() == ends.keys()
    assert (
        attempts <= allocations[0]["request_limit"] and seconds <= allocations[0]["seconds_limit"]
    )
    prior = read_json(previous)
    margin = 7200 - allocations[0]["seconds_limit"]
    cumulative_seconds = (
        prior["cumulative_model_resident_seconds"] - prior["model_resident_seconds"] + seconds
    )
    return {
        "stage": "stage2",
        "status": "complete",
        "run_identity": run.name,
        "ledger_sha256": file_hash(ledger),
        "previous_snapshot_sha256": file_hash(previous),
        "accounting_definition": "One GPU; wall time immediately before model loading until model disposal, including inference, waits and retries. CPU file checksum verification before loading is excluded. Conservatively add the frozen 30-second device-context teardown margin.",
        "authorized_ceiling": {"generation_attempts": 1500, "aggregate_gpu_seconds": 7200},
        "programmatic_guard": allocations[0],
        "sessions": list(starts),
        "generation_attempts": attempts,
        "generation_failures": sum(e["event"] == "generation_error" for e in calls),
        "generation_requests_by_purpose": dict(
            Counter(e["purpose"] for e in calls if e["event"] == "generation_start")
        ),
        "input_tokens": sum(r["input_tokens"] for r in responses),
        "output_tokens": sum(r["output_tokens"] for r in responses),
        "generation_latency_seconds": sum(r["latency_seconds"] for r in responses),
        "model_resident_seconds": seconds,
        "stage2_additional_uncertainty_seconds": margin,
        "stage2_conservative_seconds": seconds + margin,
        "cumulative_generation_attempts": prior["cumulative_generation_attempts"]
        - prior["generation_attempts"]
        + attempts,
        "cumulative_model_resident_seconds": cumulative_seconds,
        "cumulative_additional_uncertainty_upper_bound_seconds": prior[
            "cumulative_additional_uncertainty_upper_bound_seconds"
        ]
        - prior["stage2_additional_uncertainty_seconds"]
        + margin,
        "events": events,
    }


def main():
    parser = argparse.ArgumentParser()
    for name in ("run", "ledger", "previous", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    result = account(args.run, args.ledger, args.previous)
    immutable_json(args.output, result)
    print(
        {
            k: result[k]
            for k in (
                "generation_attempts",
                "model_resident_seconds",
                "cumulative_generation_attempts",
                "cumulative_model_resident_seconds",
            )
        }
    )


if __name__ == "__main__":
    main()
