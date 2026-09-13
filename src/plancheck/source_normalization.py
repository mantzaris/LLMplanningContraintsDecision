"""Source-only literal normalization, promoted from the Stage 2 offline diagnostic.

Only an existing temporal atom's value changes. Operators, scope, missing atoms,
JSON errors and unsupported reports are not repaired. No reference inputs exist.
"""

from collections import defaultdict
from copy import deepcopy
import re
from .constraints import ADAPTER
from .gtfs import seconds
from .util import canonical


def atoms(formula):
    if formula["kind"] == "atom":
        yield formula
    elif formula["kind"] == "all":
        for child in formula["children"]:
            yield from atoms(child)
    else:
        yield from atoms(formula["child"])


def time_mentions(request: str) -> list[dict]:
    names = {
        "depart no earlier than": "depart_ge",
        "do not depart before": "depart_ge",
        "depart no later than": "depart_le",
        "arrive by": "arrive_by",
    }
    pattern = re.compile(
        r"(?P<phrase>depart no earlier than|do not depart before|depart no later than|arrive by) "
        r"(?P<clock>\d{2,3}:[0-5]\d:[0-5]\d)",
        re.I,
    )
    found = []
    for match in pattern.finditer(request):
        sentence = request[request.rfind(".", 0, match.start()) + 1 : match.start()]
        scopes = re.findall(r"On the (outbound|return) segment only,", sentence, re.I)
        found.append(
            {
                "op": names[match["phrase"].lower()],
                "scope": scopes[-1].lower() if scopes else "outbound",
                "literal": match["clock"],
                "seconds": seconds(match["clock"]),
                "source": {"start": match.start(), "end": match.end()},
                "text": match.group(),
            }
        )
    return found


def normalize_time_values(request, expression):
    bindings = defaultdict(list)
    for mention in time_mentions(request):
        bindings[(mention["op"], mention["scope"])].append(mention)
    formula, changes = expression.model_dump(mode="json"), []
    for atom in atoms(formula):
        options = bindings[(atom["op"], atom["scope"])]
        if atom["unit"] == "seconds" and len(options) == 1:
            mention = options[0]
            if atom["value"] != mention["seconds"]:
                changes.append({"predicted_atom": deepcopy(atom), "request_binding": mention})
                atom["value"] = mention["seconds"]
    return ADAPTER.validate_json(canonical(formula)), changes
