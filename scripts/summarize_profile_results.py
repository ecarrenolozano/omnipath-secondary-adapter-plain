from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RESULTS_DIR = PROJECT_ROOT / "profiling" / "results"
DEFAULT_SUMMARY_PATH = DEFAULT_RESULTS_DIR / "summary.md"
METADATA_GLOB = "profile_bc_networks_*.json"
PROFILE_HEADER_PATTERN = re.compile(
    r"(?P<calls>[\d,]+) function calls "
    r"\((?P<primitive>[\d,]+) primitive calls\) "
    r"in (?P<seconds>[\d.]+) seconds",
)
PROFILE_ROW_PATTERN = re.compile(
    r"^\s*(?P<ncalls>\S+)\s+"
    r"(?P<tottime>[\d.]+)\s+"
    r"(?P<percall_tottime>[\d.]+)\s+"
    r"(?P<cumtime>[\d.]+)\s+"
    r"(?P<percall_cumtime>[\d.]+)\s+"
    r"(?P<function>.+)$",
)


def load_metadata(results_dir: Path) -> list[dict]:
    metadata_paths = sorted(
        results_dir.glob(METADATA_GLOB),
        key=lambda path: int(re.search(r"(\d+)\.json$", path.name).group(1)),
    )
    if not metadata_paths:
        raise FileNotFoundError(
            f"No {METADATA_GLOB} files found in {results_dir}. "
            "Rerun profiling to generate JSON sidecars.",
        )
    return [json.loads(path.read_text(encoding="utf-8")) for path in metadata_paths]


def parse_profile_report(report_path: Path, limit: int = 5) -> dict:
    text = report_path.read_text(encoding="utf-8")
    header = PROFILE_HEADER_PATTERN.search(text)
    rows = []
    for line in text.splitlines():
        row = PROFILE_ROW_PATTERN.match(line)
        if not row or row.group("function") == "filename:lineno(function)":
            continue
        rows.append(
            {
                "ncalls": row.group("ncalls"),
                "tottime": float(row.group("tottime")),
                "cumtime": float(row.group("cumtime")),
                "function": row.group("function"),
            },
        )
        if len(rows) == limit:
            break

    return {
        "function_calls": int(header.group("calls").replace(",", ""))
        if header
        else None,
        "primitive_calls": (
            int(header.group("primitive").replace(",", "")) if header else None
        ),
        "profile_seconds": float(header.group("seconds")) if header else None,
        "top_functions": rows,
    }


def format_number(value) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.3f}"
    if isinstance(value, int):
        return f"{value:,}"
    return str(value)


def markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    lines.extend("| " + " | ".join(row) + " |" for row in rows)
    return "\n".join(lines)


def repeated_node_mentions(diagnostics: dict) -> int | None:
    return diagnostics.get(
        "repeated_node_mentions",
        diagnostics.get("duplicate_node_mentions"),
    )


def legacy_biocypher_validation(item: dict) -> dict[str, bool | list[str]]:
    messages = item.get("validation_messages", [])
    return {
        "duplicate_nodes": any(
            "duplicate node" in message.lower()
            and not message.lower().startswith("no duplicate node")
            for message in messages
        ),
        "duplicate_edges": any(
            "duplicate edge" in message.lower()
            and not message.lower().startswith("no duplicate edge")
            for message in messages
        ),
        "missing_labels": any(
            "missing label" in message.lower()
            and not message.lower().startswith("no missing label")
            for message in messages
        ),
        "bad_relationships": any(
            "bad relationship" in message.lower() for message in messages
        ),
        "import_failed": any(
            "import failed" in message.lower() for message in messages
        ),
        "warnings": [
            message
            for message in messages
            if not message.lower().startswith("no ")
            and not message.startswith("20")
            and not message.endswith("(IDs in log):")
            and message != "Duplicate edge IDs encountered:"
        ],
        "status_messages": [
            message for message in messages if message.lower().startswith("no ")
        ],
        "raw_messages": messages,
    }


def biocypher_validation(item: dict) -> dict:
    return item.get("biocypher_validation") or legacy_biocypher_validation(item)


def format_bool(value: bool) -> str:
    return "yes" if value else "no"


def build_summary(metadata_items: list[dict]) -> str:
    enriched = []
    for item in metadata_items:
        profile = parse_profile_report(Path(item["profile_report_path"]))
        enriched.append({**item, "profile": profile})

    summary_rows = [
        [
            item["row_count"],
            format_number(item["elapsed_seconds"]),
            format_number(item["profile"]["function_calls"]),
            format_number(item["graph_counts"]["nodes"]),
            format_number(item["graph_counts"]["edges"]),
        ]
        for item in enriched
    ]

    diagnostic_rows = [
        [
            item["row_count"],
            format_number(item.get("input_diagnostics", {}).get("input_rows")),
            format_number(item.get("input_diagnostics", {}).get("unique_nodes")),
            format_number(repeated_node_mentions(item.get("input_diagnostics", {}))),
            format_number(item.get("input_diagnostics", {}).get("unique_edges")),
            format_number(item.get("input_diagnostics", {}).get("duplicate_edges")),
        ]
        for item in enriched
    ]

    validation_lines = []
    for item in enriched:
        diagnostics = item.get("input_diagnostics", {})
        diagnostic_messages = diagnostics.get("messages", [])
        if diagnostic_messages:
            validation_lines.append(f"### {item['row_count']} rows")
            validation_lines.extend(f"- {message}" for message in diagnostic_messages)

        validation = biocypher_validation(item)
        messages = validation.get("warnings", [])
        if messages:
            if not diagnostic_messages:
                validation_lines.append(f"### {item['row_count']} rows")
            validation_lines.extend(f"- {message}" for message in messages)

    biocypher_validation_rows = [
        [
            item["row_count"],
            format_bool(biocypher_validation(item).get("duplicate_nodes", False)),
            format_bool(biocypher_validation(item).get("duplicate_edges", False)),
            format_bool(biocypher_validation(item).get("missing_labels", False)),
            format_bool(biocypher_validation(item).get("bad_relationships", False)),
            format_bool(biocypher_validation(item).get("import_failed", False)),
        ]
        for item in enriched
    ]

    hotspot_rows = []
    for item in enriched:
        first_hotspot = item["profile"]["top_functions"][0]
        hotspot_rows.append(
            [
                item["row_count"],
                format_number(first_hotspot["tottime"]),
                format_number(first_hotspot["cumtime"]),
                first_hotspot["function"],
            ],
        )

    sections = [
        "# Profiling Summary",
        "## Run Summary",
        markdown_table(
            ["Rows", "Elapsed seconds", "Function calls", "Nodes", "Edges"],
            summary_rows,
        ),
        "## Input Diagnostics",
        markdown_table(
            [
                "Rows",
                "Input rows",
                "Unique nodes",
                "Repeated node mentions",
                "Unique edges",
                "Duplicate edges",
            ],
            diagnostic_rows,
        ),
        "## BioCypher Validation",
        markdown_table(
            [
                "Rows",
                "Duplicate nodes",
                "Duplicate edges",
                "Missing labels",
                "Bad relationships",
                "Import failed",
            ],
            biocypher_validation_rows,
        ),
        "## Validation Findings",
        "\n".join(validation_lines)
        if validation_lines
        else "No validation messages found.",
        "## Top Hotspot Per Run",
        markdown_table(
            ["Rows", "Total time", "Cumulative time", "Function"], hotspot_rows
        ),
    ]
    return "\n\n".join(sections) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Summarize BioCypher profiling metadata into Markdown.",
    )
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=DEFAULT_RESULTS_DIR,
        help="Directory containing profile JSON sidecars and cProfile text reports.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_SUMMARY_PATH,
        help="Markdown summary output path.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    metadata_items = load_metadata(args.results_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(build_summary(metadata_items), encoding="utf-8")
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
