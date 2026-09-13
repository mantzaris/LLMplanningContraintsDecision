"""Public-only Stage 3 mechanisms; ordinary inference cannot read annotations."""

from __future__ import annotations
from copy import deepcopy
from .budget import BudgetExceeded
from .compiler import predicate
from .constraints import ADAPTER, All, Atom, InterpretationError, parse_interpretation, syntax_key
from .judgment import parse_judgment
from .methods import finalize_output
from .prompts import translation_prompt, judgment_prompt
from .render import render_journey
from .selection import candidates, select_witness, restore_candidates
from .source_normalization import normalize_time_values, time_mentions
from .util import canonical, digest

PERSPECTIVES = (
    "",
    "",
    "Check temporal relations against the exact original words: earliest versus latest, departure versus arrival, and inclusive boundaries.",
    "Check which named journey segment each requirement applies to. Preserve explicit scope and do not add requirements for another segment.",
    "Check negation and inequality direction. A logically infeasible conjunction can still be a supported formalization; do not delete a requirement to make it feasible.",
    "Check transfer counting and each explicit resource restriction, if present. Count transfers within the named segment and do not add absent preferences.",
    "Read each source requirement in order and check that the complete formula preserves it, including any dependencies or visits that the language supports.",
    "Re-read the source literally. Check for omissions and invented restrictions. Return the best-supported complete interpretation; agreement with earlier attempts is allowed.",
)
FEEDBACK_LIMIT = 6000


def behavior(expression, pool, request):
    """Exact full and top-level conjunct behavior. Source associations are trace aids."""
    clauses = expression.children if isinstance(expression, All) else (expression,)
    rows = []
    for child in clauses:
        association = None
        if isinstance(child, Atom):
            mentions = [
                m
                for m in time_mentions(request)
                if (m["op"], m["scope"]) == (child.op, child.scope)
            ]
            if len(mentions) == 1:
                association = {"kind": "unique_source_operator_scope", **mentions[0]["source"]}
        if association is None and child.source:
            association = {"kind": "model_span_unverified", **child.source.model_dump()}
        vector = [predicate(child, j) for j in pool]
        rows.append(
            {
                "formula": child.model_dump(mode="json"),
                "signature": vector,
                "signature_hash": digest(vector),
                "source_association": association,
            }
        )
    vector = [predicate(expression, j) for j in pool]
    return {"signature": vector, "signature_hash": digest(vector), "clauses": rows}


def parse_sample(raw, scenario, pool):
    try:
        original = parse_interpretation(raw, scenario)
        expr, changes = normalize_time_values(scenario.request, original)
        return {
            "parse_status": "ok",
            "raw_formula": original.model_dump(mode="json"),
            "formula": expr.model_dump(mode="json"),
            "normalization": changes,
            "syntax_key": syntax_key(expr),
            **behavior(expr, pool, scenario.request),
        }
    except InterpretationError as error:
        return {
            "parse_status": error.status,
            "error": str(error),
            "formula": None,
            "signature": None,
            "clauses": [],
        }


def feedback(scenario, pool, samples):
    """Whitelist public sample fields; no labels, preferred output or reference access."""
    groups, clause_variants = {}, []
    for index, sample in enumerate(samples):
        if sample.get("signature") is None:
            continue
        key = sample["signature_hash"]
        group = groups.setdefault(
            key,
            {
                "first_attempt": index + 1,
                "attempts": [],
                "accepts": sum(sample["signature"]),
                "signature_hash": key,
            },
        )
        group["attempts"].append(index + 1)
        for clause in sample["clauses"]:
            variant = {
                "formula": clause["formula"],
                "accepts": sum(clause["signature"]),
                "signature_hash": clause["signature_hash"],
                "source_association": clause["source_association"],
            }
            if variant not in clause_variants:
                clause_variants.append(variant)
    parts = [
        "Executable feedback about YOUR EARLIER GENERATED INTERPRETATIONS, not correctness labels.",
        f"Exact evaluation over the shared bounded universe of {len(pool)} scheduled journeys. "
        "Matching full signatures mean agreement only here, not agreement with the source request.",
        f"Attempts so far: {len(samples)}; unparsed/failed: {sum(s.get('signature') is None for s in samples)}.",
        "Represented full behaviors (all groups; attempt lists show repetitions): "
        + canonical(list(groups.values())),
        "Separate conjunct behaviors follow so an always-false conjunct does not hide other differences. "
        "Source associations are traceability aids, not proof of faithful interpretation.",
    ]
    for variant in clause_variants:
        addition = canonical(variant)
        if len("\n".join(parts)) + len(addition) > FEEDBACK_LIMIT - 600:
            parts.append("Additional conjunct details omitted under the fixed feedback size limit.")
            break
        parts.append(addition)
    # First ID with a full disagreement; otherwise a conjunct disagreement, otherwise
    # first pool journey. No reference or natural-language correctness test is involved.
    valid = [s for s in samples if s.get("signature") is not None]
    vectors = [s["signature"] for s in valid]
    if len({tuple(v) for v in vectors}) < 2:
        vectors = [c["signature"] for s in valid for c in s["clauses"]]
    ordered = sorted(range(len(pool)), key=lambda i: pool[i].journey_id)
    example = next((i for i in ordered if len({v[i] for v in vectors}) > 1), ordered[0])
    concrete = render_journey(pool[example], scenario)
    labels = [s["signature"][example] if s.get("signature") is not None else None for s in samples]
    addition = (
        "Illustrative scheduled journey:\n"
        + concrete
        + "\nEarlier full predictions by attempt: "
        + canonical(labels)
    )
    if len("\n".join(parts)) + len(addition) <= FEEDBACK_LIMIT - 350:
        parts.append(addition)
    else:
        parts.append(
            "Concrete journey omitted under the fixed feedback limit; no partial schedule is shown."
        )
    parts.append(
        "Reconsider the ORIGINAL request, using this feedback only to inspect repeated interpretations. "
        "Do not force disagreement. Repeating any interpretation is permitted when it remains best supported. "
        "Return a complete source-faithful formula, not a plan or an invented extra requirement."
    )
    result = "\n".join(parts)
    assert len(result) <= FEEDBACK_LIMIT
    return result


def sampling_prompt(arm, index, scenario, pool, samples):
    prompt = translation_prompt(scenario)
    if arm != "A" and PERSPECTIVES[index]:
        prompt += "\nSource-focused perspective:\n" + PERSPECTIVES[index]
    if arm == "C" and index >= 2:
        prompt += "\n" + feedback(scenario, pool, samples)
    return prompt


class TokenCalls:
    """Token admission and failure caching around the existing exact-cache ModelCalls.

    Admission reserves known input plus the output limit. Success charges actual
    I+O; failures with unknown output charge the full reservation, also on replay.
    """

    def __init__(self, calls, counter=None, actual_request_limit=None):
        self.calls, self.counter = calls, counter
        self.actual_request_limit = actual_request_limit
        self.saved = {
            e["key"]: e for e in calls.journal.read() if e["event"] == "sampling_response"
        }

    def key(self, prompt, seed, maximum, temperature):
        return digest(
            {
                "prompt": prompt,
                "seed": seed,
                "max_new_tokens": maximum,
                "temperature": temperature,
                "top_p": 0.95,
                "model": self.calls.metadata,
            }
        )

    def invoke(self, prompt, seed, maximum, temperature, purpose, owner, remaining):
        key = self.key(prompt, seed, maximum, temperature)
        old = self.saved.get(key)
        size = old["known_input_tokens"] if old else self.counter(prompt) if self.counter else None
        if size is None:
            raise KeyError("Replay is missing prompt-token admission record")
        if size + maximum > remaining:
            raise BudgetExceeded("token_allowance_before_call")
        if (
            self.actual_request_limit is not None
            and old is None
            and sum(e["event"] == "generation_start" for e in self.calls.journal.read())
            >= self.actual_request_limit
        ):
            raise BudgetExceeded("development_actual_request_limit")
        if old and old["failed"]:
            record = {**deepcopy(old), "cached": True, "owner": owner}
        else:
            try:
                raw = self.calls.call(prompt, seed, maximum, temperature, purpose, owner)
                logical = self.calls.logical[-1]
                record = {
                    "event": "sampling_response",
                    "key": key,
                    "raw": raw,
                    "failed": False,
                    "known_input_tokens": size,
                    "charged_tokens": logical["input_tokens"] + logical["output_tokens"],
                    "input_tokens": logical["input_tokens"],
                    "output_tokens": logical["output_tokens"],
                    "reserved_tokens": size + maximum,
                    "latency_seconds": logical["latency_seconds"],
                    "cached": logical["cached"],
                    "owner": owner,
                    "purpose": purpose,
                }
                assert record["input_tokens"] == size
            except BudgetExceeded:
                raise
            except (RuntimeError, ValueError, TimeoutError) as error:
                record = {
                    "event": "sampling_response",
                    "key": key,
                    "raw": None,
                    "failed": True,
                    "error_type": type(error).__name__,
                    "error": str(error),
                    "known_input_tokens": size,
                    "input_tokens": size,
                    "output_tokens": None,
                    "charged_tokens": size + maximum,
                    "reserved_tokens": size + maximum,
                    "cached": False,
                    "owner": owner,
                    "purpose": purpose,
                }
            self.saved[key] = record
        self.calls.journal.append(record)
        return record


def prefix_bundle(samples, count, pool, timeout_ms):
    prefix = samples[:count]  # Later attempts are inaccessible to this constructor.
    expressions = [
        ADAPTER.validate_json(canonical(s["formula"])) for s in prefix if s.get("formula")
    ]
    active = candidates(expressions, pool, timeout_ms)
    return {
        "candidates": [c.record() for c in active],
        "attempts": len(prefix),
        "samples": prefix,
        "generation_tokens": sum(s["call"]["charged_tokens"] for s in prefix),
        "errors": [{"status": s["parse_status"]} for s in prefix if s["parse_status"] != "ok"],
    }


def validate_prefix(bundle, scenario, pool, token_calls, config, owner):
    active = restore_candidates(bundle["candidates"])
    initial = active[0] if active else None
    output = {
        **deepcopy(bundle),
        "status": "unresolved",
        "semantic_status": "unverified",
        "plan_id": None,
        "initial_plan_id": initial.plan.plan_id if initial else None,
        "witnesses": [],
        "judgments": [],
        "repairs": [],
        "events": [],
        "logical_calls": [],
    }
    used, tokens = set(), 0
    if not active:
        output["events"].append("no_valid_candidate")
    for _ in range(2 if active else 0):
        witness = select_witness(active, pool, used, "balanced")
        if witness is None:
            output["events"].append("no_distinguishing_witness_in_completed_pool")
            break
        journey = next(j for j in pool if j.journey_id == witness["journey_id"])
        prompt = judgment_prompt(scenario, journey)
        seed = config["seed"] + int(digest(journey.journey_id)[:6], 16)
        try:
            call = token_calls.invoke(
                prompt,
                seed,
                config["max_new_tokens"],
                0.0,
                "judgment",
                owner,
                config["validation_tokens_per_prefix"] - tokens,
            )
        except BudgetExceeded as error:
            if str(error) != "token_allowance_before_call":
                raise
            output["events"].append("validation_token_exhaustion")
            break
        tokens += call["charged_tokens"]
        output["logical_calls"].append(call)
        used.add(journey.journey_id)
        output["witnesses"].append(witness)
        try:
            if call["failed"]:
                raise ValueError("generation failure")
            judgment = parse_judgment(call["raw"], scenario.request).model_dump(mode="json")
        except ValueError:
            judgment = {"verdict": "uncertain", "spans": [], "reason": "invalid or failed judgment"}
            output["errors"].append(
                {
                    "status": "judgment_generation_failure"
                    if call["failed"]
                    else "malformed_judgment"
                }
            )
        output["judgments"].append(
            {"journey_id": journey.journey_id, "judgment": judgment, "raw": call["raw"]}
        )
        if judgment["verdict"] != "uncertain":
            active = [
                c
                for c in active
                if c.accepts(journey.journey_id) == (judgment["verdict"] == "satisfied")
            ]
        if not active:
            output["events"].append("all_candidates_eliminated")
            break
    finalize_output(output, active, initial)
    output["validation_tokens"] = tokens
    return output
