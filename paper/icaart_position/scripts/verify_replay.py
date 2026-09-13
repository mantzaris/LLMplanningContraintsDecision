"""Compare saved decisions exactly, allowing only replay cache provenance to change."""

import json
from pathlib import Path
from plancheck.util import file_hash

ROOT = Path(__file__).resolve().parents[3]
original = ROOT / "runs/stage3-fresh/pairs"
replay = ROOT / "runs/icaart-stage3-replay/pairs"
changes = []


def compare(left, right, path):
    if isinstance(left, dict) and isinstance(right, dict):
        assert left.keys() == right.keys(), path
        for key in left:
            compare(left[key], right[key], path + [key])
    elif isinstance(left, list) and isinstance(right, list):
        assert len(left) == len(right), path
        for index, (a, b) in enumerate(zip(left, right)):
            compare(a, b, path + [str(index)])
    elif left != right:
        assert path[-3] == "logical_calls" and path[-1] == "cached", path
        assert left is False and right is True, path
        changes.append("/".join(path))


paths = sorted(original.glob("*.json"))
assert len(paths) == 32
for path in paths:
    compare(json.loads(path.read_text()), json.loads((replay / path.name).read_text()), [path.name])
result = {
    "base_pairs": 32,
    "decision_and_logical_cost_matches": 32,
    "byte_identical_pairs": sum(file_hash(p) == file_hash(replay / p.name) for p in paths),
    "only_differences": "19 first-use judgment calls become cache hits during replay",
    "changed_cache_flags": changes,
    "new_generations": 0,
    "pair_hashes": {p.name: file_hash(replay / p.name) for p in paths},
}
assert len(changes) == 19
(ROOT / "paper/icaart_position/analysis/replay-verification.json").write_text(
    json.dumps(result, indent=2) + "\n"
)
print(
    "32/32 decisions, formulas, witnesses, judgments and logical costs identical; 19 cache-provenance flags differ."
)
