# OmniPath Secondary BioCypher Adapter

This project builds a BioCypher knowledge graph from OmniPath interaction TSV
data. It follows the BioCypher cookiecutter-style layout: configuration lives in
`config/`, the package lives in `src/`, tests live in `tests/`, and the graph
build orchestration stays in the top-level `create_knowledge_graph.py`.

## Installation

Install the project with `uv`:

```bash
uv sync
```

## Build The Knowledge Graph

Build from the latest cached or downloaded OmniPath interactions:

```bash
uv run python create_knowledge_graph.py
```

Build from a local TSV file:

```bash
uv run python create_knowledge_graph.py \
  --input-file profiling/subset_networks_100.tsv
```

## OmniPath Identifiers

The adapter keeps short protein identifiers unchanged, so UniProt-style IDs such
as `P48995` remain readable in Neo4j. OmniPath can also provide non-protein
entities such as complexes and small molecules. Some complex identifiers contain
many member IDs and can be longer than Neo4j's importer accepts for its node ID
lookup.

To keep imports reliable, the adapter uses short stable internal IDs for
non-protein entities and for any identifier longer than the import-safe limit.
The original OmniPath identifier is preserved as the `original_id` node
property.

Example:

```text
COMPLEX:O15265_O75486_..._Q9Y6J9
```

is imported with an internal ID like:

```text
omnipath:complex:a13f0f5b8e9d0c44
```

while still keeping the full source identifier in:

```text
original_id
```

Edges use the same internal ID mapping for their `source` and `target`, so node
and relationship references stay consistent.

## Profiling

Profiling samples are downloaded and extracted into `profiling/data/` before
the profiler starts. The first run downloads this cached archive:

```text
profiling/data/interactions_sampled.zip
```

The archive contains `.tsv.gz` files. The script extracts the ZIP before
profiling starts, then passes the extracted `.tsv.gz` samples directly to the
BioCypher build. Download and ZIP extraction overhead are not included in the
cProfile measurements.

Run profiling for the default downloaded samples:

```bash
uv run python -m scripts.profile_knowledge_graphs
```

Profile a custom directory of `.tsv.gz` sample files:

```bash
uv run python -m scripts.profile_knowledge_graphs --input-dir path/to/tsvs
```

The command prints a terminal summary and writes cProfile text reports to
`profiling/results/profile_bc_networks_<rows>.txt`. BioCypher decides where
knowledge graph build outputs are written from its normal configuration.

## Tests

```bash
uv run python -m compileall create_knowledge_graph.py src tests
uv run pytest
```

## Docker

The Docker workflow uses `uv` inside the BioCypher build container:

```bash
docker compose up -d
```

The build service copies `config/biocypher_docker_config.yaml` over
`config/biocypher_config.yaml`, syncs dependencies with `uv`, and runs the
top-level `create_knowledge_graph.py`.
