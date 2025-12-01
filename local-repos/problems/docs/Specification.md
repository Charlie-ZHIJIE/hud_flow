# Skid Buffer Specification

## Module Name
`skid_buffer`

## Overview
A configurable streaming interface adapter. Behavior varies based on elaboration-time parameters.

## Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `DATA_WIDTH` | 64 | Data signal width |
| `BYPASS` | 1 | Mode selector |
| `DEPTH` | 2 | Configuration parameter |

## Interface

### Inputs
- `clk`: Clock
- `rst_n`: Reset (active-low, asynchronous)
- `s_data[DATA_WIDTH-1:0]`: Input data
- `s_valid`: Input valid
- `m_ready`: Output ready

### Outputs
- `s_ready`: Input ready
- `m_data[DATA_WIDTH-1:0]`: Output data
- `m_valid`: Output valid

---

## Behavioral Specification

### Transfer Protocol

A transfer completes when `valid` and `ready` are both high on a rising clock edge.

**Key Rules:**
- Valid must not depend on ready in the same direction
- Data must remain stable while valid is high until transfer completes
- Component must preserve data ordering: output sequence = input sequence

### Mode Differentiation (BYPASS Parameter)

The component must exhibit distinct behaviors for different `BYPASS` values.

#### When BYPASS = 0

**Acceptance Behavior:**
- Initially accepts transfers freely
- After accepting N transfers without any outputs, begins blocking
- N is determined by the `DEPTH` parameter
- Resumes accepting after outputs consume data

**Timing Behavior:**
- Output does not reflect input instantaneously
- Outputs are presented from previously accepted data
- Supports continuous operation: can accept new input while producing output

**Scaling Requirement:**
- Behavior must adapt to arbitrary `DEPTH` values
- Must function correctly for DEPTH=2, 4, 8, 16, etc.
- No hardcoded assumptions

#### When BYPASS = 1

**Acceptance Behavior:**
- Initially accepts transfers freely
- After accepting without a corresponding output, blocks further inputs
- Resumes accepting after output consumes data

**Timing Behavior:**
- When not storing data: output reflects input in the same cycle
- When storing data: output reflects stored data
- Must support immediate flow-through when possible

**Capacity:**
- Limited acceptance capability (less than Mode A)

### Reset Behavior

When `rst_n = 0`:
- Must immediately stop presenting valid outputs (asynchronous)
- Must reach a clean initial state
- Upon release, must be ready to accept new transfers

### Correctness Requirements

**Ordering:**
- Every output must appear in the same order as inputs were accepted
- If inputs [D₁, D₂, D₃] are accepted in that order, outputs must be [D₁, D₂, D₃]

**Completeness:**
- Every accepted transfer must eventually produce an output
- No data may be lost
- No data may be duplicated

**Handshake Compliance:**
- Must respect ready/valid protocol at all times
- Must not violate protocol independence rules
- Must maintain data stability requirements

### Performance Expectations

- Should minimize latency where possible
- Should maximize throughput under favorable conditions  
- Mode A: Should sustain continuous operation when output is consuming
- Mode B: Should enable zero-delay forwarding when not storing

---

**Document Version**: 8.0 (Abstract Behavioral Specification)  
**Last Updated**: November 2025  
**Focus**: Observable behavior patterns without implementation concepts
