from __future__ import annotations

import argparse
import cProfile
import io
import pstats
import re
import time
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path

from create_knowledge_graph import build_knowledge_graph

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
SAMPLES_URL = "https://zenodo.org/records/21722429/files/interactions_sampled.zip?download=1"
SUMMARY_HEADER = "input_file\trows\tseconds\treport"

DEFAULT_DATA_DIR = PROJECT_ROOT / "profiling" / "data"
DEFAULT_ARCHIVE_PATH = DEFAULT_DATA_DIR / ARCHIVE_FILENAME
DEFAULT_RESULTS_DIR = PROJECT_ROOT / "profiling" / "results"


@dataclass(frozen=True)
class ProfileResult:
    row_count: str
    elapsed_seconds: float
    report_path: Path


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


def profile_input(input_file: Path, results_dir: Path) -> ProfileResult:
    row_count = row_count_from_name(input_file)
    report_path = results_dir / PROFILE_REPORT_TEMPLATE.format(row_count=row_count)

    results_dir.mkdir(parents=True, exist_ok=True)

    profiler = cProfile.Profile()
    start = time.perf_counter()
    profiler.runcall(build_knowledge_graph, input_file=input_file)
    elapsed_seconds = time.perf_counter() - start

    write_profile_report(profiler, report_path)

    return ProfileResult(
        row_count=row_count,
        elapsed_seconds=elapsed_seconds,
        report_path=report_path,
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
