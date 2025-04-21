import random
import string
from enum import Enum, auto
from itertools import chain
from typing import Optional

import pandas as pd
from biocypher._logger import logger

from omnipath_secondary_adapter.models import NetworksPanderaModel


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
    CONSENSUS_DIRECTION = "consensus_direction"
    CONSENSUS_STIMULATION = "consensus_stimulation"
    CONSENSUS_INHIBITION = "consensus_inhibition"


# ====================================================================================
# =============================   OMNIPATH ADAPTER   =================================
# ====================================================================================
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
        self._load_dataframe(validate_schema=True)

    def _load_dataframe(self, validate_schema=False) -> None:
        """
        Load the data from the given CSV and extract genes, transcription
        factors, and relationships.
        """
        logger.info("Preprocessing data.")

        schema_model = NetworksPanderaModel

        if schema_model is None:
            logger.warning(f"No schema model found!")

        try:
            self.data = pd.read_table(
                self.file_path,
                sep="\t",
                dtype=schema_model._return_pandas_dtypes() if schema_model else None,
            )
            logger.info("DataFrame successfully loaded.")
        except Exception as e:
            logger.error(f"Failed to load dataset: {e}")
            raise

        # Identify boolean columns using pandas type system
        boolean_columns = self.data.select_dtypes(include=["boolean"]).columns

        if not boolean_columns.empty:
            # Replace NaN with False and ensure dtype is bool
            self.data[boolean_columns] = (
                self.data[boolean_columns].fillna(False).astype(bool)
            )

        logger.info(f"DataFrame shape: {self.data.shape}")
        memory_mb = self.data.memory_usage(deep=True).sum() / 1024**2
        logger.info(f"Memory usage (MB): {memory_mb:.2f}")

        if not validate_schema:
            logger.info("Skipping schema validation.")
            return

        try:
            schema_model.validate(self.data)
            logger.info("DataFrame complies with the schema.")
        except Exception as e:
            logger.error(f"Schema validation failed: {e}")
            raise

    def get_nodes(self):
        """
        Returns a generator of node tuples for node types specified in the
        adapter constructor.
        """

        logger.info("Generating nodes.")

        if OmnipathAdapterNodeType.PROTEIN not in self.node_types:
            return

        self.nodes = set()
        for row in self.data.itertuples(index=False):
            for column in ["source", "target"]:
                node = Protein(fields=self.node_fields, row=row, column_id=column)
                node_id = node.get_id()
                if node_id not in self.nodes:
                    self.nodes.add(node_id)
                    yield node_id, node.get_label(), node.get_properties()

    def get_edges(self):
        """
        Returns a generator of edge tuples for edge types specified in the
        adapter constructor.

        """

        logger.info("Generating edges.")

        if not self.nodes:
            raise ValueError("No nodes found. Please run get_nodes() first.")

        if OmnipathAdapterEdgeType.PROTEIN_PROTEIN_INTERACTION not in self.edge_types:
            return

        for row in self.data.itertuples(index=False):
            edge = ProteinProteinInteractions(fields=self.edge_fields, row=row)
            yield (
                edge.get_id(),
                edge.get_source_id(),
                edge.get_target_id(),
                edge.get_label(),
                edge.get_properties(),
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
            self.edge_fields = [
                field
                for field in chain(
                    OmnipathAdapterProteinProteinEdgeField,
                )
            ]


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

    def __init__(self, fields: Optional[list] = None, row=None, column_id=None):
        self.fields = fields
        self.row = row
        self.column_id = column_id
        self.id = self._generate_id()
        self.label = "protein"
        self.properties = self._generate_properties()

    def _generate_id(self):
        """
        Generate a random UniProt-style id.
        """
        if self.column_id == "source":
            return str(self.row.source)
        if self.column_id == "target":
            return str(self.row.target)

    def _generate_properties(self):
        properties = {}

        if self.column_id == "source":

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

        if self.column_id == "target":

            if (
                self.fields is not None
                and OmnipathAdapterProteinField.GENESYMBOL in self.fields
            ):

                properties["genesymbol"] = self.row.target_genesymbol

            if (
                self.fields is not None
                and OmnipathAdapterProteinField.NCBI_TAX_ID in self.fields
            ):

                properties["ncbi_tax_id"] = self.row.ncbi_tax_id_target

            if (
                self.fields is not None
                and OmnipathAdapterProteinField.ENTITY_TYPE in self.fields
            ):
                properties["entity_type"] = self.row.entity_type_target

        return properties


class Edge:
    """
    Base class for edges.
    """

    def __init__(self):
        self.id = None
        self.source_id = None
        self.target_id = None
        self.label = None
        self.properties = {}

    def get_id(self):
        """
        Returns the node id.
        """

        return "RELID_" + self.source_id + "_" + self.target_id

    def get_source_id(self):
        """
        Returns the source id.
        """
        return self.source_id

    def get_target_id(self):
        """
        Returns the target id.
        """
        return self.target_id

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


class ProteinProteinInteractions(Edge):
    """
    Generates instances of ProteinProteinInteractions.
    """

    def __init__(self, fields: Optional[list] = None, row=None):
        self.fields = fields
        self.row = row
        self.id = self._generate_id()
        self.source_id = self._generate_source_id()
        self.target_id = self._generate_target_id()
        self.label = "protein_protein_interaction"
        self.properties = self._generate_properties()

    def _generate_id(self):
        """
        Generate a random UniProt-style id.
        """

        return str(self.row.source)

    def _generate_source_id(self):
        """
        Generate a random UniProt-style id.
        """

        return str(self.row.source)

    def _generate_target_id(self):
        """
        Generate a random UniProt-style id.
        """

        return str(self.row.target)

    def _generate_properties(self):
        properties = {}

        ## random amino acid sequence
        if (
            self.fields is not None
            and OmnipathAdapterProteinProteinEdgeField.IS_DIRECTED in self.fields
        ):
            properties["is_directed"] = self.row.is_directed

        if (
            self.fields is not None
            and OmnipathAdapterProteinProteinEdgeField.IS_STIMULATION in self.fields
        ):
            properties["is_stimulation"] = self.row.is_stimulation

        if (
            self.fields is not None
            and OmnipathAdapterProteinProteinEdgeField.IS_INHIBITION in self.fields
        ):
            properties["is_inhibition"] = self.row.is_inhibition
        if (
            self.fields is not None
            and OmnipathAdapterProteinProteinEdgeField.CONSENSUS_DIRECTION in self.fields
        ):
            properties["consensus_direction"] = self.row.consensus_direction
        if (
            self.fields is not None
            and OmnipathAdapterProteinProteinEdgeField.CONSENSUS_STIMULATION
            in self.fields
        ):
            properties["consensus_stimulation"] = self.row.consensus_stimulation
        if (
            self.fields is not None
            and OmnipathAdapterProteinProteinEdgeField.CONSENSUS_INHIBITION in self.fields
        ):
            properties["consensus_inhibition"] = self.row.consensus_inhibition

        return properties

    CONSENSUS_INHIBITION = "consensus_inhibition"
