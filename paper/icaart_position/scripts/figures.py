"""Publication figures from the paper's checksum-verified request-level analysis."""

from pathlib import Path
import hashlib
import json
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DATA, OUT = ROOT / "analysis", ROOT / "figures"
COLORS = ["#0072B2", "#D55E00", "#009E73"]
NAMES = ["Independent sampling", "Diversified sampling", "Solver-guided sampling"]
plt.rcParams.update(
    {
        "font.family": "DejaVu Sans",
        "font.size": 8,
        "axes.titlesize": 9,
        "axes.labelsize": 8,
        "xtick.labelsize": 7,
        "ytick.labelsize": 7,
        "legend.fontsize": 7,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "axes.spines.top": False,
        "axes.spines.right": False,
    }
)
OUT.mkdir(exist_ok=True)


def read(name):
    return json.loads((DATA / name).read_text())


def save(fig, name):
    fig.savefig(
        OUT / f"{name}.pdf",
        metadata={"Creator": "Matplotlib", "Author": "", "CreationDate": None},
        bbox_inches="tight",
        pad_inches=0.035,
    )
    fig.savefig(OUT / f"{name}.png", dpi=220, bbox_inches="tight", pad_inches=0.035)
    plt.close(fig)


def costs():
    data = read("stage3-summary.json")["checkpoints"]
    fig, axes = plt.subplots(1, 2, figsize=(6.15, 2.55), sharex=True, sharey=True)
    for ax, metric, title in zip(
        axes, ["G", "S"], ["(a) Matching candidate available", "(b) Correct final outcome"]
    ):
        for arm, color, marker, name in zip("ABC", COLORS, ["o", "s", "^"], NAMES):
            rows = [r for r in data if r["arm"] == arm]
            xs, ys = [r["logical_tokens"] / 32000 for r in rows], [r[metric] for r in rows]
            ax.plot(xs, ys, color=color, marker=marker, label=name, lw=1.1, ms=4)
            for r, x, y in zip(rows, xs, ys):
                if r["checkpoint"] == 2 and arm != "A":
                    continue
                offset = (0, 7) if arm == "B" else (0, -12)
                if arm == "C":
                    offset = (5, -1)
                ax.annotate(
                    str(r["checkpoint"]),
                    (x, y),
                    xytext=offset,
                    textcoords="offset points",
                    color=color,
                    fontsize=7,
                )
        ax.set_title(title, loc="left")
        ax.set_xlabel("Mean logical tokens (thousands)")
        ax.set_xticks([5, 10, 15, 20, 25])
        ax.set_ylim(23, 33)
        ax.set_yticks(
            [24, 25, 27, 28, 31, 32], ["24/32", "25/32", "27/32", "28/32", "31/32", "32/32"]
        )
        ax.grid(axis="y", alpha=0.2)
    axes[0].set_ylabel("Base requests")
    fig.legend(
        *axes[0].get_legend_handles_labels(),
        loc="upper center",
        bbox_to_anchor=(0.54, 1.09),
        ncol=3,
        frameon=False,
    )
    fig.subplots_adjust(wspace=0.12, bottom=0.22)
    save(fig, "cost-outcomes")


def joint():
    data = [r for r in read("stage3-summary.json")["checkpoints"] if r["checkpoint"] == 8]
    fig, ax = plt.subplots(figsize=(3.05, 2.65))
    fig.subplots_adjust(left=0.28, right=0.98, bottom=0.28, top=0.87)
    keys = ["G1S1", "G1S0", "G0S1", "G0S0"]
    labels = ["G=1, S=1", "G=1, S=0", "G=0, S=1", "G=0, S=0"]
    colors = ["#0072B2", "#E69F00", "#56B4E9", "#BBBBBB"]
    left = np.zeros(3)
    for key, label, color, hatch in zip(keys, labels, colors, ["", "///", "..", ""]):
        vals = [r[key] for r in data]
        ax.barh(
            range(3),
            vals,
            left=left,
            color=color,
            label=label,
            hatch=hatch,
            edgecolor="white",
            height=0.55,
        )
        for y, v, offset in zip(range(3), vals, left):
            if v:
                ax.text(
                    offset + v / 2,
                    y,
                    str(v),
                    ha="center",
                    va="center",
                    fontsize=7,
                    color="white" if key == "G1S1" else "black",
                )
        left += vals
    ax.set_yticks(range(3), ["Independent", "Diversified", "Solver-guided"])
    ax.invert_yaxis()
    ax.set_xlim(0, 32)
    ax.set_xticks([0, 8, 16, 24, 32])
    ax.set_xlabel("Base requests (32 per arm)")
    fig.legend(
        *ax.get_legend_handles_labels(),
        loc="lower center",
        bbox_to_anchor=(0.5, 0.015),
        ncol=2,
        frameon=False,
        columnspacing=0.7,
    )
    ax.set_title("Final checkpoint: eight attempts", loc="left")
    save(fig, "joint-outcomes")


def opportunity():
    x = read("stage2-summary.json")
    fig, (a, b) = plt.subplots(1, 2, figsize=(6.15, 2.25), gridspec_kw={"width_ratios": [1, 1.12]})
    values = [
        x["n"],
        x["opportunity"]["distinguishable"],
        x["opportunity"]["consequential"],
        x["opportunity"]["divergent_sequences"],
    ]
    a.barh(range(4), values, color=["#BDBDBD", "#56B4E9", "#0072B2", "#D55E00"], height=0.55)
    a.set_yticks(
        range(4), ["All requests", "Distinguishable", "Consequential", "Different sequences"]
    )
    a.invert_yaxis()
    a.set_xlim(0, 54)
    a.set_xticks([0, 16, 32, 48])
    a.set_xlabel("Nested sets of base requests")
    for y, v in enumerate(values):
        a.text(v + 1, y, str(v), va="center", fontsize=8)
    a.set_title("(a) Opportunity to change selection", loc="left")
    cov = x["clause_coverage"]
    groups = [
        ("Time", ["earliest_departure", "latest_departure", "latest_arrival"]),
        ("Transfers", ["transfer_limit"]),
        ("Modes", ["allowed_modes", "forbidden_modes"]),
        ("Visits", ["ordered_calls"]),
    ]
    left = np.zeros(4)
    for key, label, color in [
        ("separates", "Varies", "#0072B2"),
        ("always_true", "Always true", "#BDBDBD"),
        ("always_false", "Always false", "#E69F00"),
    ]:
        vals = [sum(cov[k].get(key, 0) for k in ks) for _, ks in groups]
        b.barh(range(4), vals, left=left, color=color, label=label, height=0.55)
        for y, v, offset in zip(range(4), vals, left):
            if v == 1:
                b.annotate(
                    "1",
                    (offset + v / 2, y),
                    xytext=(10, -12),
                    textcoords="offset points",
                    fontsize=7,
                    color="black",
                    arrowprops={"arrowstyle": "-", "linewidth": 0.6},
                )
            elif v:
                b.text(
                    offset + v / 2,
                    y,
                    str(v),
                    ha="center",
                    va="center",
                    fontsize=7,
                    color="white" if key == "separates" else "black",
                )
        left += vals
    b.set_yticks(range(4), [g[0] for g in groups])
    b.invert_yaxis()
    b.set_xlim(0, 58)
    b.set_xticks([0, 20, 40])
    b.set_xlabel("Reference clauses (101 total)")
    b.set_title("(b) Effective clause coverage", loc="left")
    b.legend(
        loc="upper center",
        bbox_to_anchor=(0.5, -0.32),
        ncol=3,
        frameon=False,
        columnspacing=0.7,
        handlelength=1,
    )
    fig.subplots_adjust(wspace=0.65)
    save(fig, "selector-opportunity")


def clock(seconds):
    return f"{seconds // 3600:02d}:{seconds % 3600 // 60:02d}:{seconds % 60:02d}"


def worked():
    examples = read("worked-examples.json")
    fig, axes = plt.subplots(1, 2, figsize=(6.15, 3.05))
    info = [
        (
            "sampling-12",
            "(a) Matching candidate discarded",
            "SW 5th & Hall → SE Division & 20th Ave",
            "Depart no later than 10:08:31, inclusive.",
            "After first check: d ≤ 10:08:31 or d ≥ 10:08:11",
            ["004977e99b44fd327c54", "3d2ac4bc9b683d64bff9", "23dc77966eb67609fd49"],
            ["Second witness", "Ordinary final", "Oracle final"],
            "Model: satisfied; reference: violated.\nCorrect candidate removed; wrong plan returned.",
        ),
        (
            "sampling-20",
            "(b) Correct plan without a matching candidate",
            "SE Powell & Milwaukie → SW 6th & Clay",
            "Depart no later than 10:55:00, inclusive.",
            "No matching candidate; final candidate: d ≥ 10:55",
            ["0046a48e25e956543682", "0ce2d0f97e8a8824a218", "2ba084255b08719b7312"],
            ["First witness", "Ordinary final", "Oracle final"],
            "First label wrong; second label correct.\nOrdinary final leaves exactly at the boundary.",
        ),
    ]
    for ax, (sid, title, od, request, formula, ids, labels, explanation) in zip(axes, info):
        ex = examples[sid]
        journeys = {j["journey_id"]: j for j in ex["ordinary"]["journeys"]}
        ax.set_title(title, loc="left", fontsize=8)
        ax.text(0, 1.01, od, transform=ax.transAxes, fontsize=6.7, va="top")
        ax.text(0, 0.90, request, transform=ax.transAxes, fontsize=7, va="top", fontweight="bold")
        ax.text(0, 0.80, formula, transform=ax.transAxes, fontsize=6.7, va="top")
        for y, jid, label in zip([0.58, 0.36, 0.14], ids, labels):
            j = journeys[jid]
            start = j["rides"][0]["calls"][0]["departure_s"]
            end = j["rides"][-1]["calls"][-1]["arrival_s"]
            color = (
                "#0072B2"
                if (sid == "sampling-12" and label == "Oracle final")
                or (sid == "sampling-20" and label == "Ordinary final")
                else "#D55E00"
            )
            ax.text(0, y + 0.085, label, transform=ax.transAxes, fontsize=7)
            ax.annotate(
                "",
                xy=(0.95, y),
                xytext=(0.10, y),
                xycoords="axes fraction",
                arrowprops={"arrowstyle": "->", "lw": 1.3, "color": color},
            )
            ax.text(0.10, y - 0.065, clock(start), transform=ax.transAxes, ha="center", fontsize=7)
            ax.text(0.93, y - 0.065, clock(end), transform=ax.transAxes, ha="center", fontsize=7)
            routes = " → ".join(r["route_id"] for r in j["rides"])
            ax.text(
                0.52,
                y + 0.015,
                f"Bus {routes}",
                transform=ax.transAxes,
                ha="center",
                fontsize=6.7,
                color=color,
            )
        ax.text(
            0, -0.11, explanation, transform=ax.transAxes, fontsize=7, va="top", linespacing=1.35
        )
        ax.axis("off")
    fig.subplots_adjust(wspace=0.30, bottom=0.17)
    save(fig, "worked-transit")


def main():
    costs()
    joint()
    opportunity()
    worked()
    manifest = {
        "selection_rule": "Worked cases selected illustratively for the two off-diagonal G/S cells: first diversified G1S0 at final checkpoint (sampling-12), and the sole independent G0S1 at final checkpoint (sampling-20). Not prevalence estimates.",
        "data_sha256": {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in [
                DATA / name
                for name in ["stage2-summary.json", "stage3-summary.json", "worked-examples.json"]
            ]
        },
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "figures": {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(OUT.iterdir())
            if p.suffix in {".pdf", ".png"}
        },
    }
    (ROOT / "figure-provenance.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    )


if __name__ == "__main__":
    main()
