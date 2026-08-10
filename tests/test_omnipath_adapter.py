from __future__ import annotations

from pathlib import Path

from omnipath_secondary_adapter.adapters.adapter_omnipath_networks import (
    MAX_IMPORT_ID_LENGTH,
    OmnipathAdapter,
    OmnipathAdapterEdgeType,
    OmnipathAdapterNodeType,
    OmnipathAdapterProteinField,
    OmnipathAdapterProteinProteinEdgeField,
    stable_node_id,
)


def test_adapter_generates_unique_protein_nodes(sample_networks_tsv: Path) -> None:
    adapter = OmnipathAdapter(
        node_types=[OmnipathAdapterNodeType.PROTEIN],
        node_fields=[
            OmnipathAdapterProteinField.GENESYMBOL,
            OmnipathAdapterProteinField.NCBI_TAX_ID,
            OmnipathAdapterProteinField.ENTITY_TYPE,
            OmnipathAdapterProteinField.ORIGINAL_ID,
        ],
        edge_types=[OmnipathAdapterEdgeType.POST_TRANSLATIONAL],
        file_path=str(sample_networks_tsv),
    )

    nodes = list(adapter.get_nodes())

    assert [node[0] for node in nodes] == ["P1", "P2", "P3"]
    assert all(node[1] == "protein" for node in nodes)
    assert nodes[0][2] == {
        "genesymbol": "GENE1",
        "ncbi_tax_id": 9606,
        "entity_type": "protein",
        "original_id": "P1",
    }


def test_adapter_generates_configured_protein_interaction_edges(
    sample_networks_tsv: Path,
) -> None:
    adapter = OmnipathAdapter(
        node_types=[OmnipathAdapterNodeType.PROTEIN],
        edge_types=[OmnipathAdapterEdgeType.POST_TRANSLATIONAL],
        edge_fields=[
            OmnipathAdapterProteinProteinEdgeField.IS_DIRECTED,
            OmnipathAdapterProteinProteinEdgeField.IS_STIMULATION,
            OmnipathAdapterProteinProteinEdgeField.IS_INHIBITION,
        ],
        file_path=str(sample_networks_tsv),
    )

    edges = list(adapter.get_edges())

    assert edges[0] == (
        "RELID_P1_P2_post_translational",
        "P1",
        "P2",
        "post_translational",
        {
            "is_directed": True,
            "is_stimulation": True,
            "is_inhibition": False,
        },
    )
    assert edges[0][0] == "RELID_P1_P2_post_translational"
    assert edges[1][1:4] == ("P2", "P3", "post_translational")


def test_adapter_maps_edge_labels_from_omnipath_type(sample_networks_tsv: Path) -> None:
    text = sample_networks_tsv.read_text(encoding="utf-8")
    text = text.replace("post_translational", "transcriptional", 1)
    sample_networks_tsv.write_text(text, encoding="utf-8")

    adapter = OmnipathAdapter(
        node_types=[OmnipathAdapterNodeType.PROTEIN],
        edge_types=list(OmnipathAdapterEdgeType),
        edge_fields=[OmnipathAdapterProteinProteinEdgeField.INTERACTION_TYPE],
        file_path=str(sample_networks_tsv),
    )

    edges = list(adapter.get_edges())

    assert edges[0][0] == "RELID_P1_P2_transcriptional"
    assert edges[0][3] == "transcriptional"
    assert edges[0][4] == {"type": "transcriptional"}


def test_adapter_labels_match_schema_config() -> None:
    schema_text = Path("config/schema_config.yaml").read_text(encoding="utf-8")

    assert "input_label: protein" in schema_text
    assert "input_label: post_translational" in schema_text
    assert "input_label: transcriptional" in schema_text
    assert "input_label: post_transcriptional" in schema_text
    assert "input_label: mirna_transcriptional" in schema_text
    assert "input_label: lncrna_post_transcriptional" in schema_text
    assert "input_label: small_molecule_protein" in schema_text
    assert "original_id: str" in schema_text


def test_protein_ids_remain_readable() -> None:
    assert stable_node_id("P48995", "protein") == "P48995"


def test_long_non_protein_ids_are_stably_hashed(sample_networks_tsv: Path) -> None:
    long_complex_id = "COMPLEX:" + "_".join(f"P{i:05d}" for i in range(30))
    text = sample_networks_tsv.read_text(encoding="utf-8")
    text = text.replace("P1", long_complex_id, 1)
    text = text.replace("GENE1", "COMPLEX_GENE", 1)
    text = text.replace("protein\t9606\tprotein", "complex\t9606\tcomplex", 1)
    sample_networks_tsv.write_text(text, encoding="utf-8")

    adapter = OmnipathAdapter(
        node_types=[OmnipathAdapterNodeType.PROTEIN],
        node_fields=[
            OmnipathAdapterProteinField.ENTITY_TYPE,
            OmnipathAdapterProteinField.ORIGINAL_ID,
        ],
        edge_types=[OmnipathAdapterEdgeType.POST_TRANSLATIONAL],
        file_path=str(sample_networks_tsv),
    )

    nodes = list(adapter.get_nodes())
    edges = list(adapter.get_edges())
    complex_node = nodes[0]

    assert complex_node[0].startswith("omnipath:complex:")
    assert len(complex_node[0]) < MAX_IMPORT_ID_LENGTH
    assert complex_node[2]["entity_type"] == "complex"
    assert complex_node[2]["original_id"] == long_complex_id
    assert edges[0][1] == complex_node[0]
