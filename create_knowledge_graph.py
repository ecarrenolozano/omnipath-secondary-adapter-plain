from biocypher import (
    BioCypher,
    FileDownload,
)
from omnipath_secondary_adapter.adapters.omnipath_adapter import (
    OmnipathAdapter,
    OmnipathAdapterNodeType,
    OmnipathAdapterEdgeType,
    OmnipathAdapterProteinField,
)

import pandas as pd

# -----------------------
# Step 1. Data download

bc = BioCypher()


# urls = "/home/ecarreno/SSC-Projects/b_REPOSITORIES/ecarrenolozano/omnipath-secondary-adapter/data/subset_interactions_100.tsv"
# networks_omnipath = FileDownload(
#     name="omniapth_networks",  # Name of the resource
#     url_s=urls,  # URL to the resource(s)
#     lifetime=7,  # seven days cache lifetime
# )
# paths = bc.download(networks_omnipath)  # Downloads to '.cache' by default
paths = [
    "/home/ecarreno/SSC-Projects/b_REPOSITORIES/ecarrenolozano/omnipath-secondary-adapter/data/subset_interactions_100.tsv"
]
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
    # Proteins
    OmnipathAdapterProteinField.GENESYMBOL,
    OmnipathAdapterProteinField.ENTITY_TYPE,
    OmnipathAdapterProteinField.NCBI_TAX_ID,
]

edge_types = [
    OmnipathAdapterEdgeType.PROTEIN_PROTEIN_INTERACTION,
]

# Create a protein adapter instance
adapter = OmnipathAdapter(
    # node_types=node_types,
    # node_fields=node_fields,
    # edge_types=edge_types,
    # we can leave edge fields empty, defaulting to all fields in the adapter
    file_path=paths[0],
)


# Create a knowledge graph from the adapter
bc.write_nodes(adapter.get_nodes())
bc.write_edges(adapter.get_edges())

# Write admin import statement
bc.write_import_call()

# Print summary
bc.summary()
