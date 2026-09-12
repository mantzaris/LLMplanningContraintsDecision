#!/usr/bin/env python3
"""One offline-selected, actually scheduled illustration of false infeasibility."""

from pathlib import Path
import argparse
import os
from plancheck.reference import check_reference
from plancheck.runner import load_public
from plancheck.domain import objective
from plancheck.util import immutable_json, read_json


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--public", type=Path, required=True)
    parser.add_argument("--references", type=Path, required=True)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    scenarios, pools = load_public(args.public)
    refs = {r["scenario_id"]: r["reference"] for r in read_json(args.references)}
    examples = []
    for scenario in sorted(scenarios, key=lambda s: s.scenario_id):
        output = read_json(args.run / "pairs" / f"{scenario.scenario_id}-r0.json")["outputs"]["D"][
            "4"
        ]
        feasible = [
            j for j in pools[scenario.pool_hash] if check_reference(refs[scenario.scenario_id], j)
        ]
        if output["status"] == "infeasible_in_pool" and feasible:
            examples.append((scenario, output, min(feasible, key=objective)))
    if not examples:
        raise ValueError("No actual false-infeasibility example to plot")
    scenario, output, journey = examples[0]
    os.environ.setdefault("MPLCONFIGDIR", "/tmp/plancheck-matplotlib")
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({"font.size": 10, "pdf.fonttype": 42, "svg.fonttype": "none"})
    fig, ax = plt.subplots(figsize=(7.4, 3.4))
    for i, ride in enumerate(journey.rides):
        ax.plot(
            [ride.departure / 3600, ride.arrival / 3600],
            [i, i],
            linewidth=7,
            solid_capstyle="round",
            color="#317873",
        )
        ax.text(
            ride.departure / 3600, i + 0.18, f"Route {ride.route_id} · {ride.scope}", fontsize=9
        )
    ax.set_yticks(range(len(journey.rides)), [f"Ride {i + 1}" for i in range(len(journey.rides))])
    ax.set_xticks(
        [7, 7.5, 8, 8.5, 9, 9.5, 10],
        ["07:00", "07:30", "08:00", "08:30", "09:00", "09:30", "10:00"],
    )
    ax.set(
        xlim=(7, 10),
        ylim=(-0.4, len(journey.rides) - 0.3),
        xlabel="Scheduled local time · 2026-09-14 · America/Los_Angeles",
    )
    ax.axvline(9.25, color="#a94442", linestyle="--", label="Requested return departure ≥09:15")
    ax.legend(loc="lower right", fontsize=8)
    ax.spines[["top", "right"]].set_visible(False)
    fig.suptitle(
        "Actual scheduled illustration selected offline; D and E returned no plan", fontsize=11
    )
    fig.text(
        0.08,
        0.015,
        "Natural model error: return bound 54,900 s = 15:15, outside the 07:00–10:00 pool.\nReference-feasible journey shown for explanation; never supplied to the selector.",
        fontsize=9,
    )
    fig.tight_layout(rect=(0, 0.14, 1, 0.96))
    args.output.mkdir(parents=True, exist_ok=True)
    for ext in ("pdf", "svg", "png"):
        fig.savefig(
            args.output / f"false-infeasibility-timeline.{ext}", dpi=180, bbox_inches="tight"
        )
    plt.close(fig)
    immutable_json(
        args.output / "timeline-provenance.json",
        {
            "scenario_id": scenario.scenario_id,
            "journey_id": journey.journey_id,
            "pool_hash": scenario.pool_hash,
            "feed_hash": scenario.feed_hash,
            "selection_rule": "first lexicographic saved false-infeasibility request, earliest independently feasible pool journey",
            "stage": "Stage 1 artifact reanalysis, not new pilot inference",
            "formula": output["final_formula"],
            "request": scenario.request,
            "reference": refs[scenario.scenario_id],
        },
    )


if __name__ == "__main__":
    main()
