"""Freeze pre-outcome protocol and non-schedule annotation exports."""

from pathlib import Path
import shutil
from .prompts import prompt_manifest
from .runner import source_hash, revision
from .util import digest, immutable_json, read_json


def freeze(config: dict, prepared: Path, destination: Path) -> dict:
    data = read_json(prepared / "manifest.json")
    public = read_json(prepared / "public/scenarios.json")
    references = read_json(prepared / "private/references.json")
    review = read_json(prepared / "private/automated-review.json")
    if not review["all_wording_matches"] or any(r["uncertain"] for r in review["rows"]):
        raise ValueError("Resolve wording review flags before freezing")
    if config["scenario_ids"] != data["scenario_ids"]:
        raise ValueError("Config must retain the predeclared coverage order")
    requests = [{k: v for k, v in row.items() if k != "stops"} for row in public]
    protocol = {
        "protocol_id": "stage2-controlled-v1",
        "starting_revision": "ab3e17eaaa14ac9bdc4fa54b59c7ecfb29feaca0",
        "freeze_parent_revision": revision(),
        "source_hash_at_freeze": source_hash(),
        "config": config,
        "config_hash": digest(config),
        "public_hash": digest(public),
        "reference_hash": digest(references),
        "data_manifest_hash": digest(data),
        "prompt_hash": digest(prompt_manifest()),
        "reference_version": "stage2-provisional-v1",
        "selectors": {
            "D": "sum 1 over separated unordered pairs / unit judgment cost",
            "E": "sum (1 + I_ij) over separated unordered pairs / unit judgment cost",
            "impact": "cross-rejection of each available selected plan; missing-plan contribution zero",
            "ties": "exact rational score descending, lexicographic journey ID ascending",
            "objective": "earliest final arrival, fewest boardings, earliest departure, journey ID",
            "deduplication": "ignore source spans for syntax; exact acceptance vectors in shared pool",
        },
        "principal_update": "eliminate candidates disagreeing with definite judgments; uncertain eliminates none; no model repair",
        "selection_output": "first surviving semantic class in generation order; exhausted means unresolved, initial retained diagnostically",
        "secondary": "A first translation; B one critique each replicate; C two positive/negative examples and at most one repair on replicate 0",
        "annotation_status": "assistant-authored, automatically grammar-reviewed, provisional, not human audited",
        "oracle": "separate offline exact reference labels, same elimination-only policy, no GPU repairs",
        "replication": "48 distinct OD base requests, two generation replicates; no paraphrases; all development",
        "scope_reduction": "after first four candidate-only bundles and before judging: timing forecast, 2 to 1 replicates then remove final six-base blocks",
        "statistics": "paired base-request mean differences; 10000 percentile bootstrap draws, seed 2201, replicates clustered; no confirmatory significance claim",
        "representatives": "lexicographically first tie, failure, correct output, and divergent trajectory; categories may overlap",
        "holdout": "exclude every Stage 1 selected OD pair and its reverse, including held-out segment pairs; publication holdout unrun",
        "reuse_limits": "same routes, stops, geography, date and templates overlap; distinct OD IDs do not establish population independence",
    }
    immutable_json(destination / "protocol.json", protocol)
    immutable_json(destination / "requests.json", requests)
    immutable_json(destination / "references.json", references)
    immutable_json(destination / "data-manifest.json", data)
    immutable_json(destination / "automated-review.json", review)
    immutable_json(destination / "prompts.json", prompt_manifest())
    target = destination / "annotation-review.csv"
    if not target.exists():
        shutil.copyfile(prepared / "private/annotation-review.csv", target)
    return {"protocol_hash": digest(protocol), "scenario_count": len(requests)}
