# Reconciliation Report

Input file: `/home/ecarreno/SSC-Projects/b_REPOSITORIES/ecarrenolozano/omnipath-secondary-adapter-plain/profiling/data/interactions_sampled/interactions_sampled_1000000.tsv.gz`

BioCypher output: `/home/ecarreno/SSC-Projects/b_REPOSITORIES/ecarrenolozano/omnipath-secondary-adapter-plain/biocypher-out/20260810160702`

## Summary

| Metric | Value |
| --- | --- |
| Raw node mentions | 2,000,000 |
| Unique raw nodes | 54,680 |
| Final nodes | 54,680 |
| Collapsed node mentions | 1,945,320 |
| Nodes with repeated mentions | 51,380 |
| Nodes with property conflicts | 25 |
| Nodes preserving all raw property values | 0 |
| Input edges | 1,000,000 |
| Unique input edges | 1,000,000 |
| Duplicate input edges | 0 |
| Final edges | 1,000,000 |

## Node Property Conflicts

| Property | Nodes with multiple raw values |
| --- | --- |
| genesymbol | 23 |
| ncbi_tax_id | 2 |
| entity_type | 0 |

## Most Repeated Nodes

| Node ID | Mentions | Roles |
| --- | --- | --- |
| P49711 | 7,468 | source, target |
| Q61164 | 6,864 | source, target |
| A0A8I5ZMQ8 | 6,731 | source, target |
| P18146 | 5,939 | source, target |
| P42224 | 5,891 | source, target |
| Q92754 | 5,852 | source, target |
| A0A0H2UHR3 | 5,468 | source, target |
| A0A087WSP5 | 5,455 | source, target |
| P49715 | 5,446 | source, target |
| P08046 | 5,379 | source, target |
| Q61312 | 5,351 | source, target |
| A0A8I5XWF9 | 5,344 | source, target |

## Merged Property Examples

| Node ID | Mentions | Property | Raw values | Final values | Final contains all raw values |
| --- | --- | --- | --- | --- | --- |
| P01562 | 142 | genesymbol | IFNA1, IFNA13 | IFNA13 | no |
| P68431 | 109 | genesymbol | H3C11, H3C3 | H3C3 | no |
| P62805 | 102 | genesymbol | H4C14, H4C9 | H4C9 | no |
| P84243 | 77 | genesymbol | H3-3A, H3-3B | H3-3B | no |
| Q16637 | 68 | genesymbol | SMN1, SMN2 | SMN1 | no |
| 3385 | 67 | ncbi_tax_id | -1, 9606 | 9606 | no |
| O15263 | 54 | genesymbol | DEFB4A, DEFB4B | DEFB4A | no |
| P47929 | 42 | genesymbol | LGALS7, LGALS7B | LGALS7B | no |
| P04908 | 31 | genesymbol | H2AC4, H2AC8 | H2AC8 | no |
| P0C0S8 | 30 | genesymbol | H2AC11, H2AC17 | H2AC17 | no |
| P0DN86 | 29 | genesymbol | CGB3, CGB5 | CGB3 | no |
| P62807 | 25 | genesymbol | H2BC6, H2BC8 | H2BC6 | no |
