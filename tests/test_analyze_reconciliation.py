from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from scripts.analyze_reconciliation import (
    build_markdown_report,
    build_reconciliation_analysis,
    load_largest_profile_metadata,
)


def write_input(path: Path) -> None:
    data = pd.DataFrame(
        [
            {
                "source": "P1",
                "target": "P2",
                "type": "transcriptional",
                "source_genesymbol": "A",
                "target_genesymbol": "B",
                "ncbi_tax_id_source": "9606",
                "ncbi_tax_id_target": "9606",
                "entity_type_source": "protein",
                "entity_type_target": "protein",
            },
            {
                "source": "P1",
                "target": "P3",
                "type": "post_translational",
                "source_genesymbol": "A_alt",
                "target_genesymbol": "C",
                "ncbi_tax_id_source": "9606",
                "ncbi_tax_id_target": "9606",
                "entity_type_source": "protein",
                "entity_type_target": "protein",
            },
        ],
    )
    data.to_csv(path, sep="\t", index=False)


def write_output(output_dir: Path, merged: bool) -> None:
    output_dir.mkdir()
    (output_dir / "Protein-header.csv").write_text(
        ":ID\tgenesymbol\tncbi_tax_id:long\tentity_type\t:LABEL",
        encoding="utf-8",
    )
    genesymbol = "'A, A_alt'" if merged else "'A'"
    (output_dir / "Protein-part000.csv").write_text(
        "\n".join(
            [
                f"P1\t{genesymbol}\t9606\t'protein'\t'Protein'",
                "P2\t'B'\t9606\t'protein'\t'Protein'",
                "P3\t'C'\t9606\t'protein'\t'Protein'",
            ],
        )
        + "\n",
        encoding="utf-8",
    )
    (output_dir / "Transcriptional-part000.csv").write_text(
        "P1\tP2\tTranscriptional\n",
        encoding="utf-8",
    )
    (output_dir / "PostTranslational-part000.csv").write_text(
        "P1\tP3\tPostTranslational\n",
        encoding="utf-8",
    )


def test_reconciliation_analysis_detects_merged_property_values(tmp_path: Path):
    input_file = tmp_path / "input.tsv"
    output_dir = tmp_path / "out"
    write_input(input_file)
    write_output(output_dir, merged=True)

    analysis = build_reconciliation_analysis(input_file, output_dir)

    node = analysis["node_reconciliation"]
    assert node["raw_node_mentions"] == 4
    assert node["final_nodes"] == 3
    assert node["collapsed_node_mentions"] == 1
    assert node["nodes_with_property_conflicts"] == 1
    assert node["nodes_with_all_raw_property_values_preserved"] == 1
    assert node["merged_property_examples"][0]["node_id"] == "P1"
    assert node["merged_property_examples"][0]["merged_all_raw_values"] is True


def test_reconciliation_analysis_reports_unmerged_property_values(tmp_path: Path):
    input_file = tmp_path / "input.tsv"
    output_dir = tmp_path / "out"
    write_input(input_file)
    write_output(output_dir, merged=False)

    analysis = build_reconciliation_analysis(input_file, output_dir)

    node = analysis["node_reconciliation"]
    assert node["nodes_with_property_conflicts"] == 1
    assert node["nodes_with_all_raw_property_values_preserved"] == 0
    assert node["merged_property_examples"][0]["merged_all_raw_values"] is False


def test_markdown_report_contains_reconciliation_sections(tmp_path: Path):
    input_file = tmp_path / "input.tsv"
    output_dir = tmp_path / "out"
    write_input(input_file)
    write_output(output_dir, merged=True)

    report = build_markdown_report(build_reconciliation_analysis(input_file, output_dir))

    assert "# Reconciliation Report" in report
    assert "Nodes with property conflicts" in report
    assert "Nodes preserving all raw property values" in report
    assert "Final contains all raw values" in report


def test_load_largest_profile_metadata(tmp_path: Path):
    (tmp_path / "profile_bc_networks_100.json").write_text(
        json.dumps({"row_count": "100"}),
        encoding="utf-8",
    )
    (tmp_path / "profile_bc_networks_1000.json").write_text(
        json.dumps({"row_count": "1000"}),
        encoding="utf-8",
    )

    assert load_largest_profile_metadata(tmp_path)["row_count"] == "1000"
