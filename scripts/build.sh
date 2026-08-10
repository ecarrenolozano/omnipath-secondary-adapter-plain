#!/bin/bash -c
cd /usr/app/
cp -r /src/* .
cp config/biocypher_docker_config.yaml config/biocypher_config.yaml
python3 -m pip install uv
uv sync --frozen
uv run python create_knowledge_graph.py
chmod -R 777 biocypher-log
