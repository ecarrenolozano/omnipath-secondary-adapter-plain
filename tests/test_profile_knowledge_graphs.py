from __future__ import annotations

import gzip
import json
import sys
import zipfile
from pathlib import Path

from scripts import profile_knowledge_graphs


def sample_tsv_name(row_count: int) -> str:
    return (
        f"{profile_knowledge_graphs.SAMPLE_FILENAME_PREFIX}"
        f"{row_count}"
        f"{profile_knowledge_graphs.SAMPLE_FILENAME_SUFFIX}"
    )


def write_sample(path: Path, rows: list[tuple[str, str, str, str, str]]) -> None:
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        handle.write(
            "source\ttarget\ttype\tentity_type_source\tentity_type_target\n",
        )
        for source, target, interaction_type, source_type, target_type in rows:
            handle.write(
                f"{source}\t{target}\t{interaction_type}\t{source_type}\t{target_type}\n"
            )


def test_profile_input_writes_cprofile_report(monkeypatch, tmp_path: Path) -> None:
    input_file = tmp_path / sample_tsv_name(2)
    write_sample(
        input_file,
        [
            ("P1", "P2", "post_translational", "protein", "protein"),
            ("P1", "P2", "post_translational", "protein", "protein"),
        ],
    )
    results_dir = tmp_path / "results"

    calls = []
    output_dir = tmp_path / "biocypher-out" / "run1"
    log_dir = tmp_path / "biocypher-log"
    log_path = log_dir / "biocypher-test.log"
    log_dir.mkdir()
    log_path.write_text("old run\n", encoding="utf-8")

    def fake_build_knowledge_graph(input_file: Path) -> None:
        calls.append(input_file)
        output_dir.mkdir(parents=True)
        (output_dir / "Protein-part000.csv").write_text("P1\nP2\n", encoding="utf-8")
        (output_dir / "ProteinProteinInteraction-part000.csv").write_text(
            "P1\tP2\n",
            encoding="utf-8",
        )
        with log_path.open("a", encoding="utf-8") as log:
            log.write(
                "2026-08-10 14:21:48,165\tWARNING\tmodule:_deduplicate\n"
                "Duplicate edge type protein protein interaction found.\n"
                "No duplicate nodes in input.\n"
                "Duplicate edge types encountered (IDs in log):\n"
                "Duplicate edge IDs encountered:\n"
                "No missing labels in input.\n",
            )

    monkeypatch.setattr(
        profile_knowledge_graphs,
        "build_profiled_knowledge_graph",
        fake_build_knowledge_graph,
    )
    monkeypatch.setattr(
        profile_knowledge_graphs,
        "DEFAULT_BIOCYPHER_OUTPUT_DIR",
        tmp_path / "biocypher-out",
    )
    monkeypatch.setattr(
        profile_knowledge_graphs,
        "DEFAULT_BIOCYPHER_LOG_DIR",
        log_dir,
    )

    result = profile_knowledge_graphs.profile_input(
        input_file=input_file,
        results_dir=results_dir,
    )

    assert result.row_count == "2"
    assert result.elapsed_seconds >= 0
    assert result.report_path == results_dir / "profile_bc_networks_2.txt"
    assert result.metadata_path == results_dir / "profile_bc_networks_2.json"
    assert "function calls" in result.report_path.read_text(encoding="utf-8")
    assert calls == [input_file]
    metadata = json.loads(result.metadata_path.read_text(encoding="utf-8"))
    assert metadata["graph_counts"] == {
        "nodes": 2,
        "edges": 1,
        "nodes_by_label": {"protein": 2},
        "edges_by_label": {"protein_protein_interaction": 1},
    }
    assert metadata["input_diagnostics"] == {
        "input_rows": 2,
        "node_mentions": 4,
        "unique_nodes": 2,
        "repeated_node_mentions": 2,
        "input_edges": 2,
        "unique_edges": 1,
        "duplicate_edges": 1,
        "messages": [
            (
                "Input contains 2 repeated node mentions that collapse into existing "
                "node records before BioCypher validation."
            ),
            "Input contains 1 duplicate edge.",
        ],
    }
    assert metadata["biocypher_output_dir"] == str(output_dir)
    assert metadata["biocypher_log_path"] == str(log_path)
    assert "No duplicate nodes in input." in "\n".join(metadata["validation_messages"])
    assert metadata["biocypher_validation"] == {
        "duplicate_nodes": False,
        "duplicate_edges": True,
        "missing_labels": False,
        "bad_relationships": False,
        "import_failed": False,
        "warnings": ["Duplicate edge type protein protein interaction found."],
        "status_messages": [
            "No duplicate nodes in input.",
            "No missing labels in input.",
        ],
        "raw_messages": [
            "2026-08-10 14:21:48,165\tWARNING\tmodule:_deduplicate",
            "Duplicate edge type protein protein interaction found.",
            "No duplicate nodes in input.",
            "Duplicate edge types encountered (IDs in log):",
            "Duplicate edge IDs encountered:",
            "No missing labels in input.",
        ],
    }
    assert "old run" not in "\n".join(metadata["validation_messages"])


def test_prepare_profile_inputs_reuses_cached_archive(
    monkeypatch, tmp_path: Path
) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    archive_path = data_dir / "interactions_sampled.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr(sample_tsv_name(2), "source\ttarget\nP1\tP2\n")

    downloaded_paths = []

    def fake_download(path: Path) -> Path:
        downloaded_paths.append(path)
        assert path.exists()
        return path

    monkeypatch.setattr(
        profile_knowledge_graphs, "download_profile_archive", fake_download
    )

    input_files = profile_knowledge_graphs.prepare_profile_inputs(data_dir)

    assert input_files == [data_dir / sample_tsv_name(2)]
    assert downloaded_paths == [archive_path]


def test_prepare_profile_inputs_extracts_before_profiling(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_dir = tmp_path / "data"
    source_archive = tmp_path / "source.zip"
    with zipfile.ZipFile(source_archive, "w") as archive:
        archive.writestr(
            f"nested/{sample_tsv_name(3)}",
            "source\ttarget\nP1\tP2\n",
        )

    def fake_download(path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(source_archive.read_bytes())
        return path

    monkeypatch.setattr(
        profile_knowledge_graphs,
        "download_profile_archive",
        fake_download,
    )

    input_files = profile_knowledge_graphs.prepare_profile_inputs(data_dir)

    assert input_files == [data_dir / "nested" / sample_tsv_name(3)]
    assert input_files[0].exists()


def test_main_input_dir_override_skips_download_and_extraction(
    monkeypatch,
    tmp_path: Path,
) -> None:
    input_dir = tmp_path / "inputs"
    results_dir = tmp_path / "results"
    input_dir.mkdir()
    input_file = input_dir / sample_tsv_name(2)
    write_sample(input_file, [("P1", "P2", "post_translational", "protein", "protein")])

    def fail_prepare(data_dir: Path) -> list[Path]:
        raise AssertionError("input-dir override should skip preparation")

    calls = []

    def fake_profile_input(input_file: Path, results_dir: Path):
        calls.append((input_file, results_dir))
        return profile_knowledge_graphs.ProfileResult(
            row_count="2",
            elapsed_seconds=0.01,
            report_path=results_dir / "profile_bc_networks_2.txt",
            metadata_path=results_dir / "profile_bc_networks_2.json",
        )

    monkeypatch.setattr(
        profile_knowledge_graphs, "prepare_profile_inputs", fail_prepare
    )
    monkeypatch.setattr(profile_knowledge_graphs, "profile_input", fake_profile_input)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "profile_knowledge_graphs.py",
            "--input-dir",
            str(input_dir),
            "--results-dir",
            str(results_dir),
        ],
    )

    profile_knowledge_graphs.main()

    assert calls == [(input_file, results_dir)]
