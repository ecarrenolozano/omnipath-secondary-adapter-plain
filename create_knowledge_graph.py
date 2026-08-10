from __future__ import annotations

import argparse
from pathlib import Path

from biocypher import BioCypher, FileDownload
from biocypher._get import Downloader

from omnipath_secondary_adapter.adapters.adapter_omnipath_networks import (
    OmnipathAdapter,
    OmnipathAdapterEdgeType,
    OmnipathAdapterNodeType,
    OmnipathAdapterProteinField,
    OmnipathAdapterProteinProteinEdgeField,
)

URLS_OMNIPATH_NETWORKS = {
    "networks": "https://archive.omnipathdb.org/omnipath_webservice_interactions__latest.tsv.gz",
}

CACHE_DATA_PATH = Path("data")


def download_omnipath_networks(cache_directory: Path = CACHE_DATA_PATH) -> Path:
    downloader = Downloader(cache_dir=str(cache_directory))
    networks_omnipath = FileDownload(
        name="omnipath_networks",
        url_s=URLS_OMNIPATH_NETWORKS["networks"],
        lifetime=7,
    )
    paths = downloader.download(networks_omnipath)
    return Path(paths[0])


def build_knowledge_graph(input_file: Path | None = None) -> None:
    input_path = input_file or download_omnipath_networks()
    print(f"Building knowledge graph from {input_path}")

    bc = BioCypher()

    node_types = [
        OmnipathAdapterNodeType.PROTEIN,
    ]
    node_fields = [
        OmnipathAdapterProteinField.GENESYMBOL,
        OmnipathAdapterProteinField.ENTITY_TYPE,
        OmnipathAdapterProteinField.NCBI_TAX_ID,
        OmnipathAdapterProteinField.ORIGINAL_ID,
    ]

    edge_types = list(OmnipathAdapterEdgeType)
    edge_fields = [
        OmnipathAdapterProteinProteinEdgeField.IS_DIRECTED,
        OmnipathAdapterProteinProteinEdgeField.IS_INHIBITION,
        OmnipathAdapterProteinProteinEdgeField.IS_STIMULATION,
        OmnipathAdapterProteinProteinEdgeField.CONSENSUS_DIRECTION,
        OmnipathAdapterProteinProteinEdgeField.CONSENSUS_INHIBITION,
        OmnipathAdapterProteinProteinEdgeField.CONSENSUS_STIMULATION,
        OmnipathAdapterProteinProteinEdgeField.SOURCES,
        OmnipathAdapterProteinProteinEdgeField.REFERENCES,
        OmnipathAdapterProteinProteinEdgeField.OMNIPATH,
        OmnipathAdapterProteinProteinEdgeField.KINASEEXTRA,
        OmnipathAdapterProteinProteinEdgeField.LIGRECEXTRA,
        OmnipathAdapterProteinProteinEdgeField.PATHWAYEXTRA,
        OmnipathAdapterProteinProteinEdgeField.DOROTHEA,
        OmnipathAdapterProteinProteinEdgeField.COLLECTRI,
        OmnipathAdapterProteinProteinEdgeField.TF_TARGET,
        OmnipathAdapterProteinProteinEdgeField.LNCRNA_MRNA,
        OmnipathAdapterProteinProteinEdgeField.TF_MIRNA,
        OmnipathAdapterProteinProteinEdgeField.SMALL_MOLECULE,
        OmnipathAdapterProteinProteinEdgeField.DOROTHEA_CURATED,
        OmnipathAdapterProteinProteinEdgeField.DOROTHEA_CHIPSEQ,
        OmnipathAdapterProteinProteinEdgeField.DOROTHEA_TFBS,
        OmnipathAdapterProteinProteinEdgeField.DOROTHEA_COEXP,
        OmnipathAdapterProteinProteinEdgeField.DOROTHEA_LEVEL,
        OmnipathAdapterProteinProteinEdgeField.INTERACTION_TYPE,
        OmnipathAdapterProteinProteinEdgeField.CURATION_EFFORT,
        OmnipathAdapterProteinProteinEdgeField.EXTRA_ATTRS,
        OmnipathAdapterProteinProteinEdgeField.EVIDENCES,
    ]

    adapter = OmnipathAdapter(
        node_types=node_types,
        node_fields=node_fields,
        edge_types=edge_types,
        edge_fields=edge_fields,
        file_path=str(input_path),
    )

    bc.write_nodes(adapter.get_nodes())
    bc.write_edges(adapter.get_edges())
    bc.write_import_call()
    bc.summary()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a BioCypher knowledge graph from OmniPath interactions.",
    )
    parser.add_argument(
        "--input-file",
        type=Path,
        help="Local OmniPath TSV file. If omitted, the latest OmniPath file is downloaded.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    build_knowledge_graph(input_file=args.input_file)
