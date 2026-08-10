# Profiling Summary

## Run Summary

| Rows | Elapsed seconds | Function calls | Nodes | Edges |
| --- | --- | --- | --- | --- |
| 100 | 0.798 | 1,759,498 | 190 | 100 |
| 1000 | 0.648 | 2,321,360 | 1,618 | 1,000 |
| 10000 | 1.993 | 7,890,704 | 10,162 | 10,000 |
| 100000 | 14.055 | 57,302,196 | 35,778 | 100,000 |
| 1000000 | 128.926 | 526,510,755 | 54,680 | 1,000,000 |

## Input Diagnostics

| Rows | Input rows | Unique nodes | Repeated node mentions | Unique edges | Duplicate edges |
| --- | --- | --- | --- | --- | --- |
| 100 | 100 | 190 | 10 | 100 | 0 |
| 1000 | 1,000 | 1,618 | 382 | 1,000 | 0 |
| 10000 | 10,000 | 10,162 | 9,838 | 10,000 | 0 |
| 100000 | 100,000 | 35,778 | 164,222 | 100,000 | 0 |
| 1000000 | 1,000,000 | 54,680 | 1,945,320 | 1,000,000 | 0 |

## BioCypher Validation

| Rows | Duplicate nodes | Duplicate edges | Missing labels | Bad relationships | Import failed |
| --- | --- | --- | --- | --- | --- |
| 100 | no | no | no | no | no |
| 1000 | no | no | no | no | no |
| 10000 | no | no | no | no | no |
| 100000 | no | no | no | no | no |
| 1000000 | no | no | no | no | no |

## Validation Findings

### 100 rows
- Input contains 10 repeated node mentions that collapse into existing node records before BioCypher validation.
### 1000 rows
- Input contains 382 repeated node mentions that collapse into existing node records before BioCypher validation.
### 10000 rows
- Input contains 9838 repeated node mentions that collapse into existing node records before BioCypher validation.
### 100000 rows
- Input contains 164222 repeated node mentions that collapse into existing node records before BioCypher validation.
### 1000000 rows
- Input contains 1945320 repeated node mentions that collapse into existing node records before BioCypher validation.

## Top Hotspot Per Run

| Rows | Total time | Cumulative time | Function |
| --- | --- | --- | --- |
| 100 | 0.288 | 0.288 | {method 'read' of '_ssl._SSLSocket' objects} |
| 1000 | 0.037 | 0.037 | {method 'read' of '_ssl._SSLSocket' objects} |
| 10000 | 0.153 | 0.694 | _batch_writer.py:1154(_write_single_edge_list_to_file) |
| 100000 | 1.536 | 6.931 | _batch_writer.py:1154(_write_single_edge_list_to_file) |
| 1000000 | 15.445 | 69.285 | _batch_writer.py:1154(_write_single_edge_list_to_file) |
