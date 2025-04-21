import pandas as pd

from biocypher import (
    BioCypher,
    FileDownload,
)
from biocypher._get import (
    Downloader,
)
from omnipath_secondary_adapter.adapters.adapter_omnipath_networks import (
    OmnipathAdapter,
    OmnipathAdapterNodeType,
    OmnipathAdapterEdgeType,
    OmnipathAdapterProteinField,
    OmnipathAdapterProteinProteinEdgeField,
)

URLS_OMNIPATH_NETWORKS = {
    "networks": "https://archive.omnipathdb.org/omnipath_webservice_interactions__latest.tsv.gz",
}

CACHE_DATA_PATH = "./data"

# -----------------------
# Step 1. Data download

bc = BioCypher()

# Define the directory where the data will be store
cache_directory = CACHE_DATA_PATH

# Instantiate the Downloader class
downloader = Downloader(cache_dir=cache_directory)

networks_omnipath = FileDownload(
    name="omnipath_networks",  # Name of the resource
    url_s=URLS_OMNIPATH_NETWORKS.get("networks"),  # URL to the resource(s)
    lifetime=7,  # seven days cache lifetime
)
paths = downloader.download(networks_omnipath)

# paths = ["data/subset_networks_1000000.tsv"]
# paths = ["data/subset_interactions_edgecases.tsv"]
print(paths)


# You can use the list of paths returned to read the resource into your adapter

# Choose node types to include in the knowledge graph.
# These are defined in the adapter (`adapter.py`).
node_types = [
    OmnipathAdapterNodeType.PROTEIN,
]

# Choose protein adapter fields to include in the knowledge graph.
# These are defined in the adapter (`adapter.py`).
node_fields = [
    # Proteins properties
    OmnipathAdapterProteinField.GENESYMBOL,
    OmnipathAdapterProteinField.ENTITY_TYPE,
    OmnipathAdapterProteinField.NCBI_TAX_ID,
]

edge_types = [
    OmnipathAdapterEdgeType.PROTEIN_PROTEIN_INTERACTION,
]

edge_fields = [
    # Proteins Protein properties
    OmnipathAdapterProteinProteinEdgeField.IS_DIRECTED,
    OmnipathAdapterProteinProteinEdgeField.IS_INHIBITION,
    OmnipathAdapterProteinProteinEdgeField.IS_STIMULATION,
]


# Create a protein adapter instance
adapter = OmnipathAdapter(
    node_types=node_types,
    node_fields=node_fields,
    edge_types=edge_types,
    #edge_fields=edge_fields,
    file_path=paths[0],
)


# Create a knowledge graph from the adapter
bc.write_nodes(adapter.get_nodes())
bc.write_edges(adapter.get_edges())

# Write admin import statement
bc.write_import_call()

# Print summary
bc.summary()


# Example profiling:  poetry run python -m cProfile -s time create_knowledge_graph.py > profile_10000.txt
