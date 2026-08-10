from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import summarize_profile_results

PROFILE_TEXT = """\
         1,234 function calls (1,200 primitive calls) in 0.321 seconds

   Ordered by: internal time

   ncalls  tottime  percall  cumtime  percall filename:lineno(function)
        1    0.100    0.100    0.200    0.200 writer.py:10(write_edges)
        2    0.050    0.025    0.070    0.035 adapter.py:20(get_edges)
"""


def test_build_summary_from_metadata_sidecars(tmp_path: Path) -> None:
    results_dir = tmp_path / "results"
    results_dir.mkdir()
    report_path = results_dir / "profile_bc_networks_100.json.txt"
    report_path.write_text(PROFILE_TEXT, encoding="utf-8")
    metadata_path = results_dir / "profile_bc_networks_100.json"
    metadata_path.write_text(
        json.dumps(
            {
                "input_file": "interactions_sampled_100.tsv.gz",
                "row_count": "100",
                "elapsed_seconds": 0.321,
                "profile_report_path": str(report_path),
                "biocypher_output_dir": "biocypher-out/run",
                "biocypher_log_path": "biocypher-log/log.txt",
                "graph_counts": {"nodes": 10, "edges": 20},
                "input_diagnostics": {
                    "input_rows": 25,
                    "node_mentions": 50,
                    "unique_nodes": 10,
                    "repeated_node_mentions": 40,
                    "input_edges": 25,
                    "unique_edges": 20,
                    "duplicate_edges": 5,
                    "messages": ["Input contains 5 duplicate edges."],
                },
                "biocypher_validation": {
                    "duplicate_nodes": False,
                    "duplicate_edges": True,
                    "missing_labels": False,
                    "bad_relationships": False,
                    "import_failed": False,
                    "warnings": [
                        "Duplicate edge type protein protein interaction found."
                    ],
                    "status_messages": ["No duplicate nodes in input."],
                    "raw_messages": [
                        "2026-08-10 14:21:48,165\tWARNING\tmodule:_deduplicate",
                        "Duplicate edge type protein protein interaction found.",
                        "Duplicate edge IDs encountered:",
                        "No duplicate nodes in input.",
                    ],
                },
            },
        ),
        encoding="utf-8",
    )

    metadata_items = summarize_profile_results.load_metadata(results_dir)
    summary = summarize_profile_results.build_summary(metadata_items)

    assert "| 100 | 0.321 | 1,234 | 10 | 20 |" in summary
    assert "| 100 | 25 | 10 | 40 | 20 | 5 |" in summary
    assert "| 100 | no | yes | no | no | no |" in summary
    assert "Input contains 5 duplicate edges." in summary
    assert "Duplicate edge type protein protein interaction found." in summary
    assert "WARNING\tmodule:_deduplicate" not in summary
    assert "Duplicate edge IDs encountered:" not in summary
    assert "writer.py:10(write_edges)" in summary


def test_build_summary_supports_old_duplicate_node_mentions_key(
    tmp_path: Path,
) -> None:
    results_dir = tmp_path / "results"
    results_dir.mkdir()
    report_path = results_dir / "profile_bc_networks_100.json.txt"
    report_path.write_text(PROFILE_TEXT, encoding="utf-8")
    metadata_path = results_dir / "profile_bc_networks_100.json"
    metadata_path.write_text(
        json.dumps(
            {
                "input_file": "interactions_sampled_100.tsv.gz",
                "row_count": "100",
                "elapsed_seconds": 0.321,
                "profile_report_path": str(report_path),
                "graph_counts": {"nodes": 10, "edges": 20},
                "input_diagnostics": {
                    "input_rows": 25,
                    "unique_nodes": 10,
                    "duplicate_node_mentions": 15,
                    "unique_edges": 20,
                    "duplicate_edges": 0,
                    "messages": [],
                },
                "validation_messages": [],
            },
        ),
        encoding="utf-8",
    )

    metadata_items = summarize_profile_results.load_metadata(results_dir)
    summary = summarize_profile_results.build_summary(metadata_items)

    assert "Repeated node mentions" in summary
    assert "| 100 | 25 | 10 | 15 | 20 | 0 |" in summary


def test_build_summary_structures_legacy_validation_messages(tmp_path: Path) -> None:
    results_dir = tmp_path / "results"
    results_dir.mkdir()
    report_path = results_dir / "profile_bc_networks_100.json.txt"
    report_path.write_text(PROFILE_TEXT, encoding="utf-8")
    metadata_path = results_dir / "profile_bc_networks_100.json"
    metadata_path.write_text(
        json.dumps(
            {
                "input_file": "interactions_sampled_100.tsv.gz",
                "row_count": "100",
                "elapsed_seconds": 0.321,
                "profile_report_path": str(report_path),
                "graph_counts": {"nodes": 10, "edges": 20},
                "input_diagnostics": {
                    "input_rows": 25,
                    "unique_nodes": 10,
                    "repeated_node_mentions": 15,
                    "unique_edges": 19,
                    "duplicate_edges": 1,
                    "messages": [],
                },
                "validation_messages": [
                    "2026-08-10 14:21:48,165\tWARNING\tmodule:_deduplicate",
                    "Duplicate edge type protein protein interaction found.",
                    "No duplicate nodes in input.",
                    "Duplicate edge IDs encountered:",
                    "No missing labels in input.",
                ],
            },
        ),
        encoding="utf-8",
    )

    metadata_items = summarize_profile_results.load_metadata(results_dir)
    summary = summarize_profile_results.build_summary(metadata_items)

    assert "| 100 | no | yes | no | no | no |" in summary
    assert "Duplicate edge type protein protein interaction found." in summary
    assert "WARNING\tmodule:_deduplicate" not in summary
    assert "Duplicate edge IDs encountered:" not in summary


def test_load_metadata_fails_when_sidecars_are_missing(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="Rerun profiling"):
        summarize_profile_results.load_metadata(tmp_path)
