from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Iterable

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RESULTS_DIR = PROJECT_ROOT / "profiling" / "results"
DEFAULT_REPORT_PATH = DEFAULT_RESULTS_DIR / "reconciliation.md"
DEFAULT_JSON_PATH = DEFAULT_RESULTS_DIR / "reconciliation.json"
PROFILE_METADATA_GLOB = "profile_bc_networks_*.json"
NODE_LABEL = "Protein"
NODE_PART_GLOB = f"{NODE_LABEL}-part*.csv"
NODE_HEADER_FILE = f"{NODE_LABEL}-header.csv"
PART_FILE_PATTERN = re.compile(r"-part\d+\.csv$")
SOURCE_COLUMN = "source"
TARGET_COLUMN = "target"
TYPE_COLUMN = "type"
RAW_NODE_PROPERTY_COLUMNS = {
    "genesymbol": ("source_genesymbol", "target_genesymbol"),
    "ncbi_tax_id": ("ncbi_tax_id_source", "ncbi_tax_id_target"),
    "entity_type": ("entity_type_source", "entity_type_target"),
}
INPUT_COLUMNS = (
    SOURCE_COLUMN,
    TARGET_COLUMN,
    TYPE_COLUMN,
    "source_genesymbol",
    "target_genesymbol",
    "ncbi_tax_id_source",
    "ncbi_tax_id_target",
    "entity_type_source",
    "entity_type_target",
)
FINAL_ID_COLUMN = ":ID"
FINAL_ORIGINAL_ID_COLUMN = "original_id"
FINAL_SEMANTIC_ID_COLUMN = "_semantic_id"
FINAL_VALUE_SEPARATOR = ", "
EXAMPLE_LIMIT = 12


def row_count_from_metadata_path(path: Path) -> int:
    match = re.search(r"(\d+)\.json$", path.name)
    if not match:
        raise ValueError(f"Cannot infer row count from metadata filename: {path}")
    return int(match.group(1))


def load_largest_profile_metadata(results_dir: Path) -> dict:
    metadata_paths = sorted(
        results_dir.glob(PROFILE_METADATA_GLOB),
        key=row_count_from_metadata_path,
    )
    if not metadata_paths:
        raise FileNotFoundError(
            f"No {PROFILE_METADATA_GLOB} files found in {results_dir}. "
            "Run profiling before analyzing reconciliation.",
        )
    return json.loads(metadata_paths[-1].read_text(encoding="utf-8"))


def clean_final_value(value: object) -> str:
    return str(value).strip().strip("'")


def normalise_final_columns(data: pd.DataFrame) -> pd.DataFrame:
    renamed = {}
    for column in data.columns:
        if ":" in column and not column.startswith(":"):
            renamed[column] = column.split(":", maxsplit=1)[0]
    data = data.rename(columns=renamed)
    for column in data.columns:
        data[column] = data[column].map(clean_final_value)
    return data


def read_final_nodes(output_dir: Path) -> pd.DataFrame:
    header_path = output_dir / NODE_HEADER_FILE
    part_paths = sorted(output_dir.glob(NODE_PART_GLOB))
    if not header_path.exists() or not part_paths:
        raise FileNotFoundError(
            f"Could not find {NODE_HEADER_FILE} and {NODE_PART_GLOB} in {output_dir}.",
        )

    header = header_path.read_text(encoding="utf-8").strip().split("\t")
    frames = [
        pd.read_csv(
            path,
            sep="\t",
            names=header,
            dtype=str,
            keep_default_na=False,
        )
        for path in part_paths
    ]
    data = normalise_final_columns(pd.concat(frames, ignore_index=True))
    if FINAL_ORIGINAL_ID_COLUMN in data.columns:
        data[FINAL_SEMANTIC_ID_COLUMN] = data[FINAL_ORIGINAL_ID_COLUMN].where(
            data[FINAL_ORIGINAL_ID_COLUMN] != "",
            data[FINAL_ID_COLUMN],
        )
    else:
        data[FINAL_SEMANTIC_ID_COLUMN] = data[FINAL_ID_COLUMN]
    return data


def read_input_nodes(input_file: Path) -> pd.DataFrame:
    data = pd.read_table(
        input_file,
        sep="\t",
        usecols=list(INPUT_COLUMNS),
        dtype=str,
        keep_default_na=False,
    )
    source = pd.DataFrame({SOURCE_COLUMN: data[SOURCE_COLUMN]})
    target = pd.DataFrame({SOURCE_COLUMN: data[TARGET_COLUMN]})
    for property_name, (source_column, target_column) in RAW_NODE_PROPERTY_COLUMNS.items():
        source[property_name] = data[source_column]
        target[property_name] = data[target_column]
    source["role"] = "source"
    target["role"] = "target"
    return pd.concat([source, target], ignore_index=True).rename(
        columns={SOURCE_COLUMN: "id"},
    )


def unique_nonempty(values: Iterable[object]) -> tuple[str, ...]:
    return tuple(sorted({str(value) for value in values if str(value) != ""}))


def split_final_values(value: object) -> tuple[str, ...]:
    text = clean_final_value(value)
    if text == "":
        return ()
    return tuple(part.strip() for part in text.split(FINAL_VALUE_SEPARATOR))


def raw_node_summary(raw_nodes: pd.DataFrame) -> pd.DataFrame:
    aggregations = {
        "mentions": ("id", "size"),
        "roles": ("role", lambda values: tuple(sorted(set(values)))),
    }
    for property_name in RAW_NODE_PROPERTY_COLUMNS:
        aggregations[f"raw_{property_name}_values"] = (
            property_name,
            unique_nonempty,
        )

    summary = raw_nodes.groupby("id", sort=False).agg(**aggregations).reset_index()
    summary["reconciled_mentions"] = summary["mentions"] - 1
    for property_name in RAW_NODE_PROPERTY_COLUMNS:
        summary[f"raw_{property_name}_count"] = summary[
            f"raw_{property_name}_values"
        ].map(len)
    return summary


def merged_property_examples(raw_summary: pd.DataFrame, final_nodes: pd.DataFrame) -> list[dict]:
    final_by_id = final_nodes.set_index(FINAL_SEMANTIC_ID_COLUMN, drop=False)
    examples = []
    for row in raw_summary.itertuples(index=False):
        if row.id not in final_by_id.index:
            continue
        final_row = final_by_id.loc[row.id]
        if isinstance(final_row, pd.DataFrame):
            final_row = final_row.iloc[0]

        for property_name in RAW_NODE_PROPERTY_COLUMNS:
            raw_values = tuple(getattr(row, f"raw_{property_name}_values"))
            if len(raw_values) < 2:
                continue
            final_values = split_final_values(final_row.get(property_name, ""))
            examples.append(
                {
                    "node_id": row.id,
                    "mentions": int(row.mentions),
                    "property": property_name,
                    "raw_values": list(raw_values),
                    "final_values": list(final_values),
                    "merged_all_raw_values": set(raw_values).issubset(final_values),
                },
            )
    return sorted(
        examples,
        key=lambda item: (item["merged_all_raw_values"], item["mentions"]),
        reverse=True,
    )


def edge_label_from_part_file(path: Path) -> str:
    label = PART_FILE_PATTERN.sub("", path.name)
    return re.sub(r"(?<!^)(?=[A-Z])", "_", label).lower()


def count_final_edges(output_dir: Path) -> int:
    total = 0
    for path in output_dir.glob("*-part*.csv"):
        if edge_label_from_part_file(path) == NODE_LABEL.lower():
            continue
        total += sum(1 for _ in path.open("r", encoding="utf-8"))
    return total


def edge_diagnostics(input_file: Path, output_dir: Path) -> dict:
    data = pd.read_table(
        input_file,
        sep="\t",
        usecols=[SOURCE_COLUMN, TARGET_COLUMN, TYPE_COLUMN],
        dtype=str,
        keep_default_na=False,
    )
    edge_keys = list(zip(data[SOURCE_COLUMN], data[TARGET_COLUMN], data[TYPE_COLUMN]))
    duplicate_edges = len(edge_keys) - len(set(edge_keys))
    return {
        "input_edges": len(edge_keys),
        "unique_input_edges": len(set(edge_keys)),
        "duplicate_input_edges": duplicate_edges,
        "final_edges": count_final_edges(output_dir),
    }


def build_reconciliation_analysis(input_file: Path, output_dir: Path) -> dict:
    raw_nodes = read_input_nodes(input_file)
    final_nodes = read_final_nodes(output_dir)
    raw_summary = raw_node_summary(raw_nodes)
    repeated_nodes = raw_summary[raw_summary["mentions"] > 1]
    merged_examples = merged_property_examples(raw_summary, final_nodes)
    property_conflict_nodes = {
        row.id
        for row in raw_summary.itertuples(index=False)
        if any(
            getattr(row, f"raw_{property_name}_count") > 1
            for property_name in RAW_NODE_PROPERTY_COLUMNS
        )
    }
    preserved_property_nodes = {
        example["node_id"]
        for example in merged_examples
        if example["merged_all_raw_values"]
    }

    property_conflicts = {
        property_name: int((raw_summary[f"raw_{property_name}_count"] > 1).sum())
        for property_name in RAW_NODE_PROPERTY_COLUMNS
    }

    top_repeated = repeated_nodes.sort_values("mentions", ascending=False).head(
        EXAMPLE_LIMIT,
    )

    return {
        "input_file": str(input_file),
        "biocypher_output_dir": str(output_dir),
        "node_reconciliation": {
            "raw_node_mentions": int(len(raw_nodes)),
            "unique_raw_nodes": int(len(raw_summary)),
            "final_nodes": int(len(final_nodes)),
            "collapsed_node_mentions": int(raw_summary["reconciled_mentions"].sum()),
            "nodes_with_repeated_mentions": int(len(repeated_nodes)),
            "nodes_with_property_conflicts": len(property_conflict_nodes),
            "nodes_with_all_raw_property_values_preserved": len(
                preserved_property_nodes,
            ),
            "property_conflict_counts": property_conflicts,
            "top_repeated_nodes": [
                {
                    "node_id": item.id,
                    "mentions": int(item.mentions),
                    "roles": list(item.roles),
                }
                for item in top_repeated.itertuples(index=False)
            ],
            "merged_property_examples": merged_examples[:EXAMPLE_LIMIT],
        },
        "edge_reconciliation": edge_diagnostics(input_file, output_dir),
    }


def format_number(value: object) -> str:
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


def build_markdown_report(analysis: dict) -> str:
    node = analysis["node_reconciliation"]
    edge = analysis["edge_reconciliation"]
    conflict_counts = node["property_conflict_counts"]
    summary_rows = [
        ["Raw node mentions", format_number(node["raw_node_mentions"])],
        ["Unique raw nodes", format_number(node["unique_raw_nodes"])],
        ["Final nodes", format_number(node["final_nodes"])],
        ["Collapsed node mentions", format_number(node["collapsed_node_mentions"])],
        [
            "Nodes with repeated mentions",
            format_number(node["nodes_with_repeated_mentions"]),
        ],
        [
            "Nodes with property conflicts",
            format_number(node["nodes_with_property_conflicts"]),
        ],
        [
            "Nodes preserving all raw property values",
            format_number(node["nodes_with_all_raw_property_values_preserved"]),
        ],
        ["Input edges", format_number(edge["input_edges"])],
        ["Unique input edges", format_number(edge["unique_input_edges"])],
        ["Duplicate input edges", format_number(edge["duplicate_input_edges"])],
        ["Final edges", format_number(edge["final_edges"])],
    ]
    conflict_rows = [
        [property_name, format_number(count)]
        for property_name, count in conflict_counts.items()
    ]
    repeated_rows = [
        [
            item["node_id"],
            format_number(item["mentions"]),
            ", ".join(item["roles"]),
        ]
        for item in node["top_repeated_nodes"]
    ]
    merged_rows = [
        [
            item["node_id"],
            format_number(item["mentions"]),
            item["property"],
            ", ".join(item["raw_values"]),
            ", ".join(item["final_values"]),
            "yes" if item["merged_all_raw_values"] else "no",
        ]
        for item in node["merged_property_examples"]
    ]

    sections = [
        "# Reconciliation Report",
        f"Input file: `{analysis['input_file']}`",
        f"BioCypher output: `{analysis['biocypher_output_dir']}`",
        "## Summary",
        markdown_table(["Metric", "Value"], summary_rows),
        "## Node Property Conflicts",
        markdown_table(["Property", "Nodes with multiple raw values"], conflict_rows),
        "## Most Repeated Nodes",
        markdown_table(["Node ID", "Mentions", "Roles"], repeated_rows),
        "## Merged Property Examples",
        markdown_table(
            [
                "Node ID",
                "Mentions",
                "Property",
                "Raw values",
                "Final values",
                "Final contains all raw values",
            ],
            merged_rows,
        ),
    ]
    return "\n\n".join(sections) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analyze node and edge reconciliation in generated BioCypher CSVs.",
    )
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=DEFAULT_RESULTS_DIR,
        help="Directory containing profiling JSON sidecars.",
    )
    parser.add_argument(
        "--input-file",
        type=Path,
        help="Input TSV/TSV.GZ file. Defaults to the largest profiling sidecar input.",
    )
    parser.add_argument(
        "--biocypher-output-dir",
        type=Path,
        help="BioCypher output directory. Defaults to the largest profiling sidecar output.",
    )
    parser.add_argument(
        "--report-path",
        type=Path,
        default=DEFAULT_REPORT_PATH,
        help="Markdown report path.",
    )
    parser.add_argument(
        "--json-path",
        type=Path,
        default=DEFAULT_JSON_PATH,
        help="JSON report path.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    metadata = None
    if args.input_file is None or args.biocypher_output_dir is None:
        metadata = load_largest_profile_metadata(args.results_dir)

    input_file = args.input_file or Path(metadata["input_file"])
    output_dir = args.biocypher_output_dir or Path(metadata["biocypher_output_dir"])
    analysis = build_reconciliation_analysis(input_file, output_dir)

    args.json_path.parent.mkdir(parents=True, exist_ok=True)
    args.report_path.parent.mkdir(parents=True, exist_ok=True)
    args.json_path.write_text(json.dumps(analysis, indent=2), encoding="utf-8")
    args.report_path.write_text(build_markdown_report(analysis), encoding="utf-8")

    node = analysis["node_reconciliation"]
    edge = analysis["edge_reconciliation"]
    print(f"Reconciliation report: {args.report_path}")
    print(f"Reconciliation JSON: {args.json_path}")
    print(
        "Nodes: "
        f"{node['raw_node_mentions']:,} raw mentions -> "
        f"{node['final_nodes']:,} final nodes; "
        f"{node['nodes_with_all_raw_property_values_preserved']:,} nodes preserve "
        "all raw property values.",
    )
    print(
        "Edges: "
        f"{edge['input_edges']:,} input edges -> "
        f"{edge['final_edges']:,} final edges; "
        f"{edge['duplicate_input_edges']:,} duplicate input edges.",
    )


if __name__ == "__main__":
    main()
