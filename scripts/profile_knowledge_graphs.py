from __future__ import annotations

import argparse
import cProfile
import io
import json
import pstats
import re
import time
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ARCHIVE_FILENAME = "interactions_sampled.zip"
BIOCYPHER_OUTPUT_WAIT_MARGIN_SECONDS = 0.01
PROFILE_REPORT_TEMPLATE = "profile_bc_networks_{row_count}.txt"
PROFILE_SORT_KEY = "time"
SAMPLE_FILENAME_PREFIX = "interactions_sampled_"
SAMPLE_FILENAME_SUFFIX = ".tsv.gz"
SAMPLE_FILENAME_GLOB = f"{SAMPLE_FILENAME_PREFIX}*{SAMPLE_FILENAME_SUFFIX}"
SAMPLE_ROW_COUNT_PATTERN = re.compile(
    rf"{re.escape(SAMPLE_FILENAME_PREFIX)}(\d+){re.escape(SAMPLE_FILENAME_SUFFIX)}$",
)
SAMPLES_URL = (
    "https://zenodo.org/records/21722429/files/interactions_sampled.zip?download=1"
)
SUMMARY_HEADER = "input_file\trows\tseconds\treport"
EDGE_LABEL = "protein_protein_interaction"
SOURCE_COLUMN = "source"
TARGET_COLUMN = "target"
SOURCE_ENTITY_TYPE_COLUMN = "entity_type_source"
TARGET_ENTITY_TYPE_COLUMN = "entity_type_target"
DIAGNOSTIC_COLUMNS = (
    SOURCE_COLUMN,
    TARGET_COLUMN,
    SOURCE_ENTITY_TYPE_COLUMN,
    TARGET_ENTITY_TYPE_COLUMN,
)
VALIDATION_MESSAGE_PATTERNS = (
    "duplicate",
    "missing labels",
    "bad relationship",
    "import failed",
    "warning",
)
LOG_METADATA_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d+\t[A-Z]+\tmodule:",
)

DEFAULT_DATA_DIR = PROJECT_ROOT / "profiling" / "data"
DEFAULT_ARCHIVE_PATH = DEFAULT_DATA_DIR / ARCHIVE_FILENAME
DEFAULT_BIOCYPHER_OUTPUT_DIR = PROJECT_ROOT / "biocypher-out"
DEFAULT_BIOCYPHER_LOG_DIR = PROJECT_ROOT / "biocypher-log"
DEFAULT_RESULTS_DIR = PROJECT_ROOT / "profiling" / "results"


@dataclass(frozen=True)
class ProfileResult:
    row_count: str
    elapsed_seconds: float
    report_path: Path
    metadata_path: Path


def existing_children(directory: Path) -> set[Path]:
    if not directory.exists():
        return set()
    return {path.resolve() for path in directory.iterdir()}


def log_offsets(directory: Path) -> dict[Path, int]:
    if not directory.exists():
        return {}
    return {
        path.resolve(): path.stat().st_size
        for path in directory.iterdir()
        if path.is_file()
    }


def detect_created_path(directory: Path, before: set[Path]) -> Path | None:
    if not directory.exists():
        return None
    created = [path for path in directory.iterdir() if path.resolve() not in before]
    if not created:
        return None
    return max(created, key=lambda path: path.stat().st_mtime)


def detect_written_log(directory: Path, before_offsets: dict[Path, int]) -> Path | None:
    if not directory.exists():
        return None

    candidates = []
    for path in directory.iterdir():
        if not path.is_file():
            continue
        resolved = path.resolve()
        previous_size = before_offsets.get(resolved, 0)
        current_size = path.stat().st_size
        if current_size > previous_size:
            candidates.append(path)

    if not candidates:
        return None

    return max(candidates, key=lambda path: path.stat().st_mtime)


def count_csv_rows(paths: list[Path]) -> int:
    return sum(sum(1 for _ in path.open("r", encoding="utf-8")) for path in paths)


def graph_counts(output_dir: Path | None) -> dict[str, int | None]:
    if output_dir is None or not output_dir.exists():
        return {"nodes": None, "edges": None}
    return {
        "nodes": count_csv_rows(sorted(output_dir.glob("Protein-part*.csv"))),
        "edges": count_csv_rows(
            sorted(output_dir.glob("ProteinProteinInteraction-part*.csv")),
        ),
    }


def read_log_segment(log_path: Path | None, before_offsets: dict[Path, int]) -> str:
    if log_path is None or not log_path.exists():
        return ""

    previous_size = before_offsets.get(log_path.resolve(), 0)
    with log_path.open("r", encoding="utf-8", errors="replace") as handle:
        handle.seek(previous_size)
        return handle.read()


def validation_messages(log_text: str) -> list[str]:
    messages = []
    for line in log_text.splitlines():
        lower_line = line.lower()
        if any(pattern in lower_line for pattern in VALIDATION_MESSAGE_PATTERNS):
            messages.append(line.strip())
    return messages


def biocypher_validation(log_text: str) -> dict[str, bool | list[str]]:
    raw_messages = validation_messages(log_text)
    meaningful_messages = [
        message
        for message in raw_messages
        if not is_log_metadata(message) and not is_validation_section_header(message)
    ]

    return {
        "duplicate_nodes": any(
            message == "Duplicate nodes encountered (IDs in log):"
            or "duplicate node type" in message.lower()
            for message in raw_messages
        ),
        "duplicate_edges": any(
            "duplicate edge type" in message.lower()
            or message == "Duplicate edge IDs encountered:"
            for message in raw_messages
        ),
        "missing_labels": not any(
            message == "No missing labels in input." for message in raw_messages
        )
        and any("missing label" in message.lower() for message in raw_messages),
        "bad_relationships": any(
            "bad relationship" in message.lower() for message in raw_messages
        ),
        "import_failed": any(
            "import failed" in message.lower() for message in raw_messages
        ),
        "warnings": [
            message
            for message in meaningful_messages
            if not message.lower().startswith("no ")
        ],
        "status_messages": [
            message
            for message in meaningful_messages
            if message.lower().startswith("no ")
        ],
        "raw_messages": raw_messages,
    }


def is_log_metadata(message: str) -> bool:
    return bool(LOG_METADATA_PATTERN.match(message))


def is_validation_section_header(message: str) -> bool:
    return message in {
        "Duplicate edge types encountered (IDs in log):",
        "Duplicate edge IDs encountered:",
        "Duplicate nodes encountered (IDs in log):",
    }


def input_diagnostics(input_file: Path) -> dict[str, int | list[str]]:
    from omnipath_secondary_adapter.adapters.adapter_omnipath_networks import (
        stable_node_id,
    )

    data = pd.read_table(input_file, sep="\t", usecols=list(DIAGNOSTIC_COLUMNS))
    source_ids = [
        stable_node_id(raw_id, entity_type)
        for raw_id, entity_type in zip(
            data[SOURCE_COLUMN],
            data[SOURCE_ENTITY_TYPE_COLUMN],
            strict=True,
        )
    ]
    target_ids = [
        stable_node_id(raw_id, entity_type)
        for raw_id, entity_type in zip(
            data[TARGET_COLUMN],
            data[TARGET_ENTITY_TYPE_COLUMN],
            strict=True,
        )
    ]
    node_ids = source_ids + target_ids
    edge_ids = [
        (source_id, target_id, EDGE_LABEL)
        for source_id, target_id in zip(source_ids, target_ids, strict=True)
    ]

    repeated_node_mentions = len(node_ids) - len(set(node_ids))
    duplicate_edges = len(edge_ids) - len(set(edge_ids))

    return {
        "input_rows": len(data),
        "node_mentions": len(node_ids),
        "unique_nodes": len(set(node_ids)),
        "repeated_node_mentions": repeated_node_mentions,
        "input_edges": len(edge_ids),
        "unique_edges": len(set(edge_ids)),
        "duplicate_edges": duplicate_edges,
        "messages": diagnostic_messages(repeated_node_mentions, duplicate_edges),
    }


def diagnostic_messages(
    repeated_node_mentions: int,
    duplicate_edges: int,
) -> list[str]:
    messages = []
    if repeated_node_mentions:
        messages.append(
            f"Input contains {repeated_node_mentions} repeated node "
            f"{pluralise('mention', repeated_node_mentions)} that collapse into "
            "existing node records before BioCypher validation.",
        )
    if duplicate_edges:
        messages.append(
            f"Input contains {duplicate_edges} "
            f"duplicate {pluralise('edge', duplicate_edges)}.",
        )
    return messages


def pluralise(noun: str, count: int) -> str:
    return noun if count == 1 else f"{noun}s"


def count_data_rows(path: Path) -> int:
    line_count = sum(1 for _ in path.open("r", encoding="utf-8"))
    return max(line_count - 1, 0)


def row_count_from_name(path: Path) -> str:
    match = SAMPLE_ROW_COUNT_PATTERN.search(path.name)
    if match:
        return match.group(1)
    return str(count_data_rows(path))


def find_profile_inputs(input_dir: Path) -> list[Path]:
    return sorted(input_dir.rglob(SAMPLE_FILENAME_GLOB))


def no_inputs_message(input_dir: Path) -> str:
    return f"No {SAMPLE_FILENAME_GLOB} files found in {input_dir}"


def download_profile_archive(archive_path: Path = DEFAULT_ARCHIVE_PATH) -> Path:
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    if archive_path.exists():
        return archive_path

    print(f"Downloading profiling samples to {archive_path}")
    urllib.request.urlretrieve(SAMPLES_URL, archive_path)
    return archive_path


def extract_profile_archive(archive_path: Path, data_dir: Path) -> None:
    print(f"Extracting profiling samples into {data_dir}")
    with zipfile.ZipFile(archive_path) as archive:
        archive.extractall(data_dir)


def prepare_profile_inputs(data_dir: Path = DEFAULT_DATA_DIR) -> list[Path]:
    data_dir.mkdir(parents=True, exist_ok=True)
    archive_path = download_profile_archive(data_dir / ARCHIVE_FILENAME)

    input_files = find_profile_inputs(data_dir)
    if not input_files:
        extract_profile_archive(archive_path, data_dir)
        input_files = find_profile_inputs(data_dir)

    if not input_files:
        raise FileNotFoundError(no_inputs_message(data_dir))

    return input_files


def write_profile_report(profiler: cProfile.Profile, report_path: Path) -> None:
    stream = io.StringIO()
    stats = pstats.Stats(profiler, stream=stream)
    stats.strip_dirs().sort_stats(PROFILE_SORT_KEY).print_stats()
    report_path.write_text(stream.getvalue(), encoding="utf-8")


def metadata_report_path(results_dir: Path, row_count: str) -> Path:
    return results_dir / f"profile_bc_networks_{row_count}.json"


def write_metadata(
    *,
    input_file: Path,
    row_count: str,
    elapsed_seconds: float,
    report_path: Path,
    output_dir: Path | None,
    log_path: Path | None,
    log_text: str,
    diagnostics: dict[str, int | list[str]],
    metadata_path: Path,
) -> None:
    metadata = {
        "input_file": str(input_file),
        "row_count": row_count,
        "elapsed_seconds": elapsed_seconds,
        "profile_report_path": str(report_path),
        "biocypher_output_dir": str(output_dir) if output_dir is not None else None,
        "biocypher_log_path": str(log_path) if log_path is not None else None,
        "graph_counts": graph_counts(output_dir),
        "input_diagnostics": diagnostics,
        "validation_messages": validation_messages(log_text),
        "biocypher_validation": biocypher_validation(log_text),
    }
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")


def build_profiled_knowledge_graph(input_file: Path) -> None:
    from create_knowledge_graph import build_knowledge_graph

    build_knowledge_graph(input_file=input_file)


def profile_input(input_file: Path, results_dir: Path) -> ProfileResult:
    row_count = row_count_from_name(input_file)
    report_path = results_dir / PROFILE_REPORT_TEMPLATE.format(row_count=row_count)
    metadata_path = metadata_report_path(results_dir, row_count)

    results_dir.mkdir(parents=True, exist_ok=True)
    diagnostics = input_diagnostics(input_file)

    output_dirs_before = existing_children(DEFAULT_BIOCYPHER_OUTPUT_DIR)
    logs_before = log_offsets(DEFAULT_BIOCYPHER_LOG_DIR)

    profiler = cProfile.Profile()
    start = time.perf_counter()
    profiler.runcall(build_profiled_knowledge_graph, input_file=input_file)
    elapsed_seconds = time.perf_counter() - start

    write_profile_report(profiler, report_path)
    output_dir = detect_created_path(DEFAULT_BIOCYPHER_OUTPUT_DIR, output_dirs_before)
    log_path = detect_written_log(DEFAULT_BIOCYPHER_LOG_DIR, logs_before)
    log_text = read_log_segment(log_path, logs_before)
    write_metadata(
        input_file=input_file,
        row_count=row_count,
        elapsed_seconds=elapsed_seconds,
        report_path=report_path,
        output_dir=output_dir,
        log_path=log_path,
        log_text=log_text,
        diagnostics=diagnostics,
        metadata_path=metadata_path,
    )

    return ProfileResult(
        row_count=row_count,
        elapsed_seconds=elapsed_seconds,
        report_path=report_path,
        metadata_path=metadata_path,
    )


def wait_until_next_second() -> None:
    now = time.time()
    sleep_seconds = (int(now) + 1) - now + BIOCYPHER_OUTPUT_WAIT_MARGIN_SECONDS
    time.sleep(sleep_seconds)


def resolve_profile_inputs(input_dir: Path | None) -> list[Path]:
    if input_dir is None:
        return prepare_profile_inputs(DEFAULT_DATA_DIR)

    input_files = find_profile_inputs(input_dir)
    if not input_files:
        raise FileNotFoundError(no_inputs_message(input_dir))

    return input_files


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Profile full BioCypher KG creation across OmniPath TSV subsets.",
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=None,
        help=f"Directory containing {SAMPLE_FILENAME_GLOB} files. Skips download and extraction.",
    )
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=DEFAULT_RESULTS_DIR,
        help="Directory where profiling reports are written.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_files = resolve_profile_inputs(args.input_dir)

    print(SUMMARY_HEADER)
    for index, input_file in enumerate(input_files):
        if index > 0:
            wait_until_next_second()

        result = profile_input(
            input_file=input_file,
            results_dir=args.results_dir,
        )
        print(
            f"{input_file}\t{result.row_count}\t"
            f"{result.elapsed_seconds:.3f}\t{result.report_path}",
        )


if __name__ == "__main__":
    main()
