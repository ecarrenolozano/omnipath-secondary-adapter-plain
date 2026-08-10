from __future__ import annotations

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


def test_profile_input_writes_cprofile_report(monkeypatch, tmp_path: Path) -> None:
    input_file = tmp_path / sample_tsv_name(2)
    input_file.write_text("source\ttarget\nP1\tP2\nP2\tP3\n", encoding="utf-8")
    results_dir = tmp_path / "results"

    calls = []

    def fake_build_knowledge_graph(input_file: Path) -> None:
        calls.append(input_file)

    monkeypatch.setattr(
        profile_knowledge_graphs,
        "build_knowledge_graph",
        fake_build_knowledge_graph,
    )

    result = profile_knowledge_graphs.profile_input(
        input_file=input_file,
        results_dir=results_dir,
    )

    assert result.row_count == "2"
    assert result.elapsed_seconds >= 0
    assert result.report_path == results_dir / "profile_bc_networks_2.txt"
    assert "function calls" in result.report_path.read_text(encoding="utf-8")
    assert calls == [input_file]


def test_prepare_profile_inputs_reuses_cached_archive(monkeypatch, tmp_path: Path) -> None:
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

    monkeypatch.setattr(profile_knowledge_graphs, "download_profile_archive", fake_download)

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
    input_file.write_text("source\ttarget\nP1\tP2\n", encoding="utf-8")

    def fail_prepare(data_dir: Path) -> list[Path]:
        raise AssertionError("input-dir override should skip preparation")

    calls = []

    def fake_profile_input(input_file: Path, results_dir: Path):
        calls.append((input_file, results_dir))
        return profile_knowledge_graphs.ProfileResult(
            row_count="2",
            elapsed_seconds=0.01,
            report_path=results_dir / "profile_bc_networks_2.txt",
        )

    monkeypatch.setattr(profile_knowledge_graphs, "prepare_profile_inputs", fail_prepare)
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
