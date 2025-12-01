# Slicing CRC Module Specification

## 1. Overview

This document specifies the `slicing_crc` module, a high-throughput CRC-32 calculator optimized for Ethernet applications. The module uses precomputed lookup tables to process multiple data bytes per clock cycle.

## 2. References

- IEEE 802.3 Ethernet Standard (CRC-32 specification)
- Sarwate, D. V. "A Computation of Cyclic Redundancy Checks via Table Look-Up"
- Kounavis, M. E. and Berry, F. L. "A Systematic Approach to Building High Performance Software-based CRC Generators"

## 3. Module Interface

### 3.1 Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `SLICE_LENGTH` | int | 8 | Number of data bytes processed per clock cycle (1-16) |
| `INITIAL_CRC` | int | 32'hFFFFFFFF | Initial value loaded into CRC register on reset |
| `INVERT_OUTPUT` | bit | 1 | When set, output is bitwise inverted |
| `REGISTER_OUTPUT` | bit | 1 | When set, output is registered; otherwise combinational |

### 3.2 Ports

| Port | Direction | Width | Description |
|------|-----------|-------|-------------|
| `i_clk` | input | 1 | System clock |
| `i_reset` | input | 1 | Synchronous reset, active high |
| `i_data` | input | 8×SLICE_LENGTH | Packed data bytes, LSB is byte 0 |
| `i_valid` | input | SLICE_LENGTH | Per-byte valid indicators |
| `o_crc` | output | 32 | CRC-32 result |

## 4. CRC-32 Background

### 4.1 Polynomial

The module computes CRC-32 using the standard Ethernet polynomial:
- Polynomial: `0x04C11DB7`
- The CRC is computed with bit reflection and final inversion per IEEE 802.3

### 4.2 Standard Byte-at-a-Time Algorithm

The traditional CRC algorithm processes one byte at a time:

```
crc = INITIAL_CRC
for each byte in data:
    index = (crc XOR byte) AND 0xFF
    crc = (crc >> 8) XOR table[index]
output = NOT crc
```

This approach is limited to one byte per clock cycle.

## 5. Slicing-by-N Algorithm

### 5.1 Concept

The slicing-by-N algorithm processes N bytes simultaneously by using N different lookup tables. Each table is precomputed to account for the polynomial shifts that would occur if bytes were processed sequentially.

### 5.2 Table Organization

The lookup tables in `crc_tables.mem` are organized as follows:
- 16 tables (Table 0 through Table 15)
- Each table contains 256 entries (one for each possible byte value)
- Each entry is a 32-bit value
- Table 0 is the standard CRC lookup table
- Tables 1-15 contain values pre-shifted for multi-byte processing

### 5.3 Algorithm Description

When processing N valid bytes in parallel:

1. **Determine byte count**: Count how many contiguous valid bytes are present (call this `num_bytes`)

2. **Compute lookup indices**: For each valid byte position `i` (0 to num_bytes-1):
   - If `i < 4`: XOR the data byte with the corresponding byte of the current CRC state
   - If `i >= 4`: Use the data byte directly (CRC state is only 4 bytes wide)

3. **Select tables**: Each byte position uses a different table:
   - Byte at position 0 uses table `[num_bytes - 1]`
   - Byte at position 1 uses table `[num_bytes - 2]`
   - Byte at position `i` uses table `[num_bytes - i - 1]`
   
4. **Perform lookups**: Look up each index in its corresponding table

5. **Combine results**: XOR all table lookup results together

6. **Handle partial CRC**: If `num_bytes < 4`, the upper bytes of the previous CRC state were not consumed. These must be XORed into the result:
   - Shift the previous CRC right by `(8 * num_bytes)` bits
   - XOR this shifted value with the combined table results

7. **Update state**: Store the result as the new CRC state

### 5.4 Example: Processing 2 Bytes

Given:
- Previous CRC: `0xAABBCCDD`
- Data bytes: `[0x12, 0x34]` (byte 0 = 0x12, byte 1 = 0x34)
- num_bytes = 2

Computation:
1. Index for byte 0: `0x12 XOR 0xDD` = `0xCF` → lookup in table[1]
2. Index for byte 1: `0x34 XOR 0xCC` = `0xF8` → lookup in table[0]
3. Combined = table[1][0xCF] XOR table[0][0xF8]
4. Since num_bytes < 4: Combined = Combined XOR (0xAABBCCDD >> 16) = Combined XOR 0x0000AABB
5. New CRC = Combined

## 6. Functional Requirements

### 6.1 Reset Behavior

When `i_reset` is asserted:
- CRC state SHALL be initialized to `INITIAL_CRC`
- State update occurs on the rising edge of `i_clk`

### 6.2 Data Processing

- Valid bytes SHALL be contiguous starting from byte 0
- `i_valid[n]` indicates whether byte n contains valid data
- When no valid bits are set, CRC state SHALL remain unchanged

### 6.3 Output Behavior

| REGISTER_OUTPUT | INVERT_OUTPUT | Output |
|-----------------|---------------|--------|
| 1 | 1 | ~(registered CRC state) |
| 1 | 0 | registered CRC state |
| 0 | 1 | ~(combinational result) |
| 0 | 0 | combinational result |

## 7. Test Vectors

The following test cases SHALL produce the specified CRC values (with default parameters):

| Input Data (hex) | Expected CRC (hex) |
|------------------|-------------------|
| 00 | D202EF8D |
| 00 00 00 00 | 2144DF1C |
| 01 02 03 04 05 06 07 08 | 3FCA88C5 |
| "123456789" (ASCII) | CBF43926 |

## 8. Implementation Constraints

- The module SHALL use `$readmemh` to load tables from `crc_tables.mem`
- The module SHALL NOT modify the lookup table contents
- The module SHALL support any SLICE_LENGTH from 1 to 16

---

**Document Version**: 2.1  
**Classification**: Engineering Specification  
**Status**: Released
