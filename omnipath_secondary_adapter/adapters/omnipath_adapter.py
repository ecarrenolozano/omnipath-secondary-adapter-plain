import random
import string
from enum import Enum, auto
from itertools import chain
from typing import Optional
from biocypher._logger import logger

import pandas as pd

logger.debug(f"Loading module {__name__}.")


class OmnipathAdapterNodeType(Enum):
    """
    Define types of nodes the adapter can provide.
    """

    PROTEIN = auto()


class OmnipathAdapterProteinField(Enum):
    """
    Define possible fields the adapter can provide for proteins.
    """

    GENESYMBOL = "genesymbol"
    NCBI_TAX_ID = "ncbi_tax_id"
    ENTITY_TYPE = "entity_type"


class OmnipathAdapterEdgeType(Enum):
    """
    Enum for the types of the protein adapter.
    """

    PROTEIN_PROTEIN_INTERACTION = "protein_protein_interaction"


class OmnipathAdapterProteinProteinEdgeField(Enum):
    """
    Define possible fields the adapter can provide for protein-protein edges.
    """

    IS_DIRECTED = "is_directed"
    IS_STIMULATION = "is_stimulation"
    IS_INHIBITION = "is_inhibition"


class OmnipathAdapter:
    """
    Example BioCypher adapter. Generates nodes and edges for creating a
    knowledge graph.

    Args:
        node_types: List of node types to include in the result.
        node_fields: List of node fields to include in the result.
        edge_types: List of edge types to include in the result.
        edge_fields: List of edge fields to include in the result.
    """

    def __init__(
        self,
        node_types: Optional[list] = None,
        node_fields: Optional[list] = None,
        edge_types: Optional[list] = None,
        edge_fields: Optional[list] = None,
        file_path: str = None,
    ):
        self.file_path = file_path
        self._set_types_and_fields(
            node_types,
            node_fields,
            edge_types,
            edge_fields,
        )
        self._preprocess_data()

    def _preprocess_data(self) -> None:
        """
        Load the data from the given CSV and extract genes, transcription
        factors, and relationships.
        """
        logger.info("Preprocessing data.")

        # load data
        self.data = pd.read_table(self.file_path)

        # extract genes (unique entities of `target` column)
        # self.genes = self.data["target"].unique()

        # extract transcription factors (unique entities of `source` column and
        # the `TF.category` column)
        # self.tf_df = self.data[["source", "TF.category"]].drop_duplicates()

    def get_nodes(self):
        """
        Returns a generator of node tuples for node types specified in the
        adapter constructor.
        """

        logger.info("Generating nodes.")

        self.nodes = []

        if OmnipathAdapterNodeType.PROTEIN in self.node_types:
            [
                self.nodes.append(Protein(fields=self.node_fields, row=row))
                for row in self.data.itertuples(index=False)
            ]

        for node in self.nodes:
            print(
                type(node.get_id()),
                type(node.get_label()),
                type(node.get_properties()),
            )
            yield (
                node.get_id(),
                node.get_label(),
                node.get_properties(),
            )

    def get_edges(self, probability: float = 0.3):
        """
        Returns a generator of edge tuples for edge types specified in the
        adapter constructor.

        Args:
            probability: Probability of generating an edge between two nodes.
        """

        logger.info("Generating edges.")

        if not self.nodes:
            raise ValueError("No nodes found. Please run get_nodes() first.")

        for node in self.nodes:
            if random.random() < probability:
                other_node = random.choice(self.nodes)

                # generate random relationship id by choosing upper or lower
                # letters and integers, length 10, and joining them
                relationship_id = "".join(
                    random.choice(string.ascii_letters + string.digits) for _ in range(10)
                )

                # determine type of edge from other_node type
                if (
                    isinstance(other_node, Protein)
                    and OmnipathAdapterEdgeType.PROTEIN_PROTEIN_INTERACTION
                    in self.edge_types
                ):
                    edge_type = OmnipathAdapterEdgeType.PROTEIN_PROTEIN_INTERACTION.value
                elif (
                    isinstance(other_node, Disease)
                    and OmnipathAdapterEdgeType.PROTEIN_DISEASE_ASSOCIATION
                    in self.edge_types
                ):
                    edge_type = OmnipathAdapterEdgeType.PROTEIN_DISEASE_ASSOCIATION.value
                else:
                    continue

                yield (
                    relationship_id,
                    node.get_id(),
                    other_node.get_id(),
                    edge_type,
                    {"example_property": "example_value"},
                )

    def get_node_count(self):
        """
        Returns the number of nodes generated by the adapter.
        """
        return len(list(self.get_nodes()))

    def _set_types_and_fields(self, node_types, node_fields, edge_types, edge_fields):
        if node_types:
            self.node_types = node_types
        else:
            self.node_types = [type for type in OmnipathAdapterNodeType]

        if node_fields:
            self.node_fields = node_fields
        else:
            self.node_fields = [
                field
                for field in chain(
                    OmnipathAdapterProteinField,
                )
            ]

        if edge_types:
            self.edge_types = edge_types
        else:
            self.edge_types = [type for type in OmnipathAdapterEdgeType]

        if edge_fields:
            self.edge_fields = edge_fields
        else:
            self.edge_fields = [field for field in chain()]


class Node:
    """
    Base class for nodes.
    """

    def __init__(self):
        self.id = None
        self.label = None
        self.properties = {}

    def get_id(self):
        """
        Returns the node id.
        """
        return self.id

    def get_label(self):
        """
        Returns the node label.
        """
        return self.label

    def get_properties(self):
        """
        Returns the node properties.
        """
        return self.properties


class Protein(Node):
    """
    Generates instances of proteins.
    """

    def __init__(self, fields: Optional[list] = None, row=None):
        self.fields = fields
        self.row = row
        self.id = self._generate_id()
        self.label = "protein"
        self.properties = self._generate_properties()
        self.row = row

    def _generate_id(self):
        """
        Generate a random UniProt-style id.
        """

        return str(self.row.source)

    def _generate_properties(self):
        properties = {}

        ## random amino acid sequence
        if (
            self.fields is not None
            and OmnipathAdapterProteinField.GENESYMBOL in self.fields
        ):
            properties["genesymbol"] = self.row.source_genesymbol

        if (
            self.fields is not None
            and OmnipathAdapterProteinField.NCBI_TAX_ID in self.fields
        ):
            properties["ncbi_tax_id"] = self.row.ncbi_tax_id_source

        if (
            self.fields is not None
            and OmnipathAdapterProteinField.ENTITY_TYPE in self.fields
        ):
            properties["entity_type"] = self.row.entity_type_source

        return properties


# class Disease(Node):
#     """
#     Generates instances of diseases.
#     """

#     def __init__(self, fields: Optional[list] = None):
#         self.fields = fields
#         self.id = self._generate_id()
#         self.label = "do_disease"
#         self.properties = self._generate_properties()

#     def _generate_id(self):
#         """
#         Generate a random disease id.
#         """
#         nums = [random.choice(string.digits) for _ in range(8)]

#         return f"DOID:{''.join(nums)}"

#     def _generate_properties(self):
#         properties = {}

#         ## random name
#         if self.fields is not None and ExampleAdapterDiseaseField.NAME in self.fields:
#             properties["name"] = " ".join(
#                 [random.choice(string.ascii_lowercase) for _ in range(10)],
#             )

#         ## random description
#         if (
#             self.fields is not None
#             and ExampleAdapterDiseaseField.DESCRIPTION in self.fields
#         ):
#             properties["description"] = " ".join(
#                 [random.choice(string.ascii_lowercase) for _ in range(10)],
#             )

#         return properties
