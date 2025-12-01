# CRC-32 Problem Repository

This is the problem repository that gets mounted into the Docker container.

## Structure

```
problems/
├── docs/
│   └── Specification.md    # Behavioral specification
├── sources/
│   ├── slicing_crc.sv      # Module to implement
│   └── crc_tables.mem      # CRC lookup tables
├── tests/
│   └── test_slicing_crc_hidden.py  # Hidden test suite
└── pyproject.toml
```

## Usage

The agent edits `sources/slicing_crc.sv` to implement the CRC calculator.
Tests are run automatically via `grade_problem()`.

