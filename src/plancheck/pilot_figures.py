"""Reproducible vector research figures from offline artifacts, with explicit provenance."""

from pathlib import Path
import os
from .util import read_json


def figures(analysis: Path, output: Path, label: str) -> dict:
    os.environ.setdefault("MPLCONFIGDIR", "/tmp/plancheck-matplotlib")
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update(
        {
            "font.size": 10,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "pdf.fonttype": 42,
            "svg.fonttype": "none",
            "savefig.dpi": 180,
        }
    )
    output.mkdir(parents=True, exist_ok=True)
    summary = read_json(analysis / "summary.json")
    diagnostics = read_json(analysis / "selector-diagnostics.json")

    def save(fig, name):
        fig.suptitle(label, fontsize=10, y=1.03)
        fig.tight_layout()
        for ext in ("pdf", "svg", "png"):
            fig.savefig(
                output / f"{name}.{ext}",
                bbox_inches="tight",
                metadata={"Creator": "plancheck saved-artifact analysis"} if ext == "pdf" else None,
            )
        plt.close(fig)

    model = [r for r in summary["summaries"] if r["mode"] == "model_judged"]
    oracle = [r for r in summary["summaries"] if r["mode"] == "oracle_diagnostic"]
    fig, ax = plt.subplots(figsize=(5.5, 3.2))
    for method, style in (("D", "o-"), ("E", "x--")):
        ax.plot(
            [r["budget"] for r in model],
            [r["methods"][method]["correct_rate"] * 100 for r in model],
            style,
            label="D balanced" if method == "D" else "E consequence",
            linewidth=1.8,
            markersize=7,
        )
    ax.set(
        xlabel="Allowed validation judgments",
        ylabel="Correct resolution (%)",
        ylim=(-2, 102),
        xticks=[0, 1, 2, 4],
    )
    ax.legend()
    save(fig, "correct-resolution")
    fig, ax = plt.subplots(figsize=(5.5, 3.2))
    budgets = [r["budget"] for r in model]
    bottom = [0] * len(model)
    for key, name, color in (
        ("paired_E_wins", "E wins", "#317873"),
        ("paired_ties", "Ties", "#aab2bd"),
        ("paired_E_losses", "E losses", "#a94442"),
    ):
        values = [r[key] for r in model]
        ax.bar([str(b) for b in budgets], values, bottom=bottom, label=name, color=color)
        bottom = [a + b for a, b in zip(bottom, values)]
    ax.set(xlabel="Allowed validation judgments", ylabel="Paired request outputs")
    ax.legend()
    save(fig, "paired-outcomes")
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.1))
    axes[0].bar(
        ["Variable\nweights", "Different\nfirst choice", "Different\ntrajectory"],
        [
            sum(d["variable_weights"] for d in diagnostics),
            sum(d["different_choice"] for d in diagnostics),
            sum(d.get("trajectory_diverged", False) for d in diagnostics),
        ],
        color="#587998",
    )
    axes[0].set(ylabel="Candidate bundles", ylim=(0, max(1, len(diagnostics))))
    counts = {n: sum(d["semantic_classes"] == n for d in diagnostics) for n in range(5)}
    axes[1].bar(list(counts), list(counts.values()), color="#808d64")
    axes[1].set(xlabel="Distinct semantic classes", ylabel="Candidate bundles", xticks=list(counts))
    save(fig, "selector-degeneracy")
    fig, ax = plt.subplots(figsize=(5.5, 3.2))
    for rows, name, marker in (
        (model, "Model-judged runtime", "o-"),
        (oracle, "Oracle diagnostic", "x--"),
    ):
        ax.plot(
            [r["budget"] for r in rows],
            [r["methods"]["E"]["correct_rate"] * 100 for r in rows],
            marker,
            label=name,
            markersize=7,
        )
    ax.set(
        xlabel="Allowed validation judgments",
        ylabel="E correct resolution (%)",
        ylim=(-2, 102),
        xticks=[0, 1, 2, 4],
    )
    ax.legend()
    save(fig, "model-versus-oracle")
    return {"figures": 4, "formats": ["pdf", "svg", "png"], "source": str(analysis), "label": label}
