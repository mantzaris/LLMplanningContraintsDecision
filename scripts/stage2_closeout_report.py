#!/usr/bin/env python3
"""Render the closeout narrative and tables from the saved CPU audit only."""

from __future__ import annotations

import argparse
from pathlib import Path

from plancheck.util import file_hash, immutable_json, read_json


def render(analysis: Path, report: Path):
    summary = read_json(analysis / "summary.json")
    assert (
        summary["requests_audited"],
        summary["clear_annotation_errors"],
        summary["unresolved_annotation_cases"],
        summary["changed_categories"],
    ) == (48, 0, 0, 0)
    tables = (analysis / "tables.md").read_text().strip().split("\n\n")
    assert len(tables) == 4
    report_text = Path(__file__).with_suffix(".md").read_text()
    for marker, table in zip(("ANNOTATIONS", "FAMILIES", "MODES", "RESULTS"), tables):
        report_text = report_text.replace("@" + marker + "@", table)
    for key, value in {
        "TRANSFER_OPTION_CASES": len(summary["requests_with_0_and_1_transfer_options"]),
        "ROUTE_CHANGE_CASES": len(summary["requests_with_route_changes"]),
        "STOP_SET_CASES": len(summary["requests_with_different_stop_sets"]),
        "FULLY_VACUOUS_CASES": len(summary["entire_request_always_satisfied"]),
        "SAME_ROUTE_TRANSFERS": summary["transfer_memberships"]["same_route"],
        "ROUTE_CHANGE_TRANSFERS": summary["transfer_memberships"]["route_change"],
    }.items():
        report_text = report_text.replace("@" + key + "@", str(value))
    assert "@" not in report_text
    report.parent.mkdir(parents=True, exist_ok=True)
    if report.exists() and report.read_text() != report_text:
        raise ValueError("Refusing changed report identity")
    report.write_text(report_text)
    immutable_json(
        analysis / "report-reproduction.json",
        {
            "renderer_sha256": file_hash(Path(__file__)),
            "template_sha256": file_hash(Path(__file__).with_suffix(".md")),
            "report_sha256": file_hash(report),
            "analysis_inputs": {
                p.name: file_hash(p)
                for p in sorted(analysis.glob("*.json"))
                if p.name not in {"report-reproduction.json", "verification.json"}
            },
            "tables_sha256": file_hash(analysis / "tables.md"),
        },
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--analysis", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    render(args.analysis, args.report)
