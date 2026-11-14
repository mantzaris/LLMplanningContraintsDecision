"""Export exact implementation text and a checked example for the companion PDF.

Run from the repository root with .venv/bin/python. No model is loaded.
"""
from pathlib import Path
import inspect
import json
import hashlib
from plancheck import prompts, semantic_sampling, render, source_normalization
from plancheck.constraints import Interpretation, parse_interpretation
from plancheck.domain import PublicScenario
from plancheck.sampling_run import protocol_prompts
from plancheck.util import canonical

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
for name, actual in (("pilot", prompts.prompt_manifest()), ("sampling", protocol_prompts())):
    saved = json.loads((ROOT / "data" / name / "prompts.json").read_text())
    assert canonical(saved) == canonical(actual), f"Frozen {name} prompt manifest differs"


def write(name, text):
    (OUT / name).write_text(text)


write("translation-instructions.txt", prompts.LANGUAGE)
write("translation-prompt.py.txt", inspect.getsource(prompts.translation_prompt))
write("judgment-prompt.py.txt", inspect.getsource(prompts.judgment_prompt))
write("journey-renderer.py.txt", inspect.getsource(render.clock_text) + "\n" + inspect.getsource(render.render_journey))
write("sampling-prompt.py.txt", inspect.getsource(semantic_sampling.sampling_prompt))
write("feedback.py.txt", inspect.getsource(semantic_sampling.feedback))
write("normalization.py.txt", inspect.getsource(source_normalization.time_mentions) + "\n" + inspect.getsource(source_normalization.normalize_time_values))
write("perspectives.json", json.dumps(semantic_sampling.PERSPECTIVES, indent=2) + "\n")
write("schema.json", canonical(Interpretation.model_json_schema()))

example = {
    "status": "ok",
    "formula": {
        "kind": "all",
        "children": [
            {"kind": "atom", "op": "arrive_by", "scope": "outbound", "value": 32400, "unit": "seconds", "source": None},
            {"kind": "atom", "op": "max_transfers", "scope": "outbound", "value": 1, "unit": "count", "source": None},
        ],
    },
    "unsupported": [],
}
scenario = PublicScenario.model_validate_json(json.dumps({
    "scenario_id": "illustration", "base_id": "illustration", "split": "development",
    "request": "On the outbound segment only, arrive by 09:00:00 with at most one transfer.",
    "authorship": "illustrative example for reproducibility companion, not an experimental request",
    "service_date": "2026-09-14", "timezone": "America/Los_Angeles",
    "stops": {"origin": "Origin", "destination": "Destination"},
    "segments": [{"scope": "outbound", "origin": "origin", "destination": "destination", "start_s": 25200, "end_s": 36000}],
    "pool_hash": "illustrative", "feed_hash": "illustrative", "max_rides_per_segment": 2,
    "minimum_connection_s": 120, "pool_complete": False,
}))
parse_interpretation(json.dumps(example), scenario)
write("example.json", json.dumps(example, indent=2) + "\n")
example_display = '''{
  "status":"ok",
  "formula":{"kind":"all","children":[
    {"kind":"atom","op":"arrive_by","scope":"outbound",
     "value":32400,"unit":"seconds","source":null},
    {"kind":"atom","op":"max_transfers","scope":"outbound",
     "value":1,"unit":"count","source":null}
  ]},
  "unsupported":[]
}
'''
assert json.loads(example_display) == example
write("example-display.json", example_display)
write("example-scenario.json", scenario.model_dump_json(indent=2) + "\n")
write("example-translation-prompt.txt", prompts.translation_prompt(scenario))
files = sorted(p for p in OUT.iterdir() if p.is_file() and p.name != "manifest.json")
write("manifest.json", json.dumps({
    "example_parser_check": "passed",
    "frozen_prompt_manifest_checks": {"data/pilot/prompts.json": "passed", "data/sampling/prompts.json": "passed"},
    "experimental_inference_calls": 0,
    "files": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
}, indent=2) + "\n")
print("Exported exact templates and schema; illustrative formula passes parse_interpretation.")
