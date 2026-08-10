from __future__ import annotations

from pathlib import Path

import create_knowledge_graph


class FakeBioCypher:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.nodes = []
        self.edges = []
        self.import_call_written = False
        self.summary_called = False

    def write_nodes(self, nodes):
        self.nodes = list(nodes)

    def write_edges(self, edges):
        self.edges = list(edges)

    def write_import_call(self):
        self.import_call_written = True

    def summary(self):
        self.summary_called = True


def test_build_knowledge_graph_uses_local_input_without_download(
    monkeypatch,
    sample_networks_tsv: Path,
) -> None:
    instances = []

    def fake_biocypher(**kwargs):
        instance = FakeBioCypher(**kwargs)
        instances.append(instance)
        return instance

    def fail_download():
        raise AssertionError("download should not run when input_file is provided")

    monkeypatch.setattr(create_knowledge_graph, "BioCypher", fake_biocypher)
    monkeypatch.setattr(create_knowledge_graph, "download_omnipath_networks", fail_download)

    create_knowledge_graph.build_knowledge_graph(input_file=sample_networks_tsv)

    assert instances[0].kwargs == {}
    assert [node[0] for node in instances[0].nodes] == ["P1", "P2", "P3"]
    assert len(instances[0].edges) == 2
    assert instances[0].import_call_written is True
    assert instances[0].summary_called is True
