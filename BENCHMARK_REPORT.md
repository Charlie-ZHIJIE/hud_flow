# MAC RX Stream Benchmark Report

## 1. Problem Overview

### 1.1 Problem Description
The MAC RX Stream problem requires implementing an Ethernet MAC receive path component (`rx_mac_stream.sv`) that:
- Receives streaming data via AXI-Stream interface
- **Instantiates the `slicing_crc` submodule** to compute CRC-32
- Verifies computed CRC against received FCS (Frame Check Sequence)
- Reports CRC status via `m_axis_tuser` (1=OK, 0=error)

### 1.2 Difficulty Level
**Advanced** - This is a hierarchical design problem requiring:
1. Submodule instantiation (`slicing_crc`)
2. State machine implementation (IDLE, DATA)
3. AXI-Stream protocol understanding
4. CRC reset timing control
5. Edge case handling (single-beat frames, back-to-back frames)

### 1.3 Key Challenges
| Challenge | Description |
|-----------|-------------|
| Hierarchical Design | Must correctly instantiate `slicing_crc` with proper parameters |
| CRC Reset Timing | `crc_reset = (state == S_IDLE) && !s_axis_tvalid` |
| Single-Beat Frames | Handle `tlast=1` on first beat in IDLE state |
| Combinational Output | Use `REGISTER_OUTPUT=0` for same-cycle CRC comparison |

---

## 2. Test Suite

### 2.1 Test Cases (10 total)

| # | Test Name | Description | Difficulty |
|---|-----------|-------------|------------|
| 1 | `test_reset_behavior` | Verify reset initialization | Easy |
| 2 | `test_single_frame_crc_ok` | Single frame with valid CRC | Medium |
| 3 | `test_single_frame_crc_error` | Single frame with invalid CRC | Medium |
| 4 | `test_fcs_not_valid` | Frame with `i_rx_fcs_valid=0` | Medium |
| 5 | `test_multiple_frames` | Multiple consecutive frames | Medium |
| 6 | `test_partial_last_beat` | Frame with partial last beat | Medium |
| 7 | `test_minimum_frame` | Single-beat minimum frame | Hard |
| 8 | `test_long_frame` | 64-byte frame | Medium |
| 9 | `test_random_frames` | Random payload tests | Medium |
| 10 | `test_back_to_back_frames` | Back-to-back frames with no gap | Hard |

### 2.2 Baseline Performance
- **Baseline Score**: 1/10 (only `test_reset_behavior` passes)
- **Baseline Implementation**: Placeholder outputs (all zeros)

---

## 3. Evaluation Results

### 3.1 Summary Statistics

| Metric | Value |
|--------|-------|
| **Overall Mean Reward** | **0.907 ± 0.202** |
| **Min/Max** | 0.40 / 1.00 |
| **Total Episodes** | 15 |
| **Model** | claude-sonnet-4-5-20250929 |
| **Max Steps** | 150 |

### 3.2 Score Distribution

| Score | Count | Percentage |
|-------|-------|------------|
| **1.00 (10/10)** | **11** | **73.3%** |
| 0.90 (9/10) | 2 | 13.3% |
| 0.40 (4/10) | 2 | 13.3% |

### 3.3 Success Rate Analysis

| Threshold | Count | Rate |
|-----------|-------|------|
| **= 1.00 (Perfect)** | **11** | **73.3%** |
| ≥ 0.90 (Near Perfect) | 13 | **86.7%** |
| ≥ 0.70 (Passing) | 13 | **86.7%** |
| > 0.20 (Improvement) | 15 | **100%** |

### 3.4 First Attempt vs Final Result

All agents started with **2/10** (0.20) on their first attempt, demonstrating:
- Baseline only passes reset test
- Agents successfully iterate and improve
- Debug report system provides actionable feedback

---

## 4. Comparison with CRC-32 Problem

| Metric | CRC-32 | MAC RX |
|--------|--------|--------|
| **Difficulty** | Medium | **Advanced** |
| **Mean Reward** | ~0.95 | 0.907 |
| **100% Success** | ~90% | 73.3% |
| **≥90% Success** | ~100% | 86.7% |
| **Requires Submodule** | No | **Yes** |
| **State Machine** | No | **Yes** |

### 4.1 Why MAC RX is Harder

1. **Hierarchical Design**: Must instantiate `slicing_crc` with correct parameters
2. **State Machine**: Requires FSM implementation (IDLE → DATA → IDLE)
3. **CRC Reset Timing**: Critical timing for `crc_reset` signal
4. **Edge Cases**: Single-beat frames, back-to-back frames
5. **Protocol Understanding**: AXI-Stream handshaking

---

## 5. Hint System Design

### 5.1 Test-Specific Hints

| Test | Hint |
|------|------|
| `test_reset_behavior` | After reset, `m_axis_tvalid` should be 0. State machine should be in IDLE state. |
| `test_single_frame_crc_ok` | Instantiate `slicing_crc` with `REGISTER_OUTPUT=0` for combinational CRC output. |
| `test_single_frame_crc_error` | When computed CRC doesn't match `i_rx_fcs`, set `m_axis_tuser=0`. |
| `test_fcs_not_valid` | When `i_rx_fcs_valid=0`, always report CRC error (`m_axis_tuser=0`). |
| `test_multiple_frames` | CRC must reset between frames. Use: `crc_reset = (state == S_IDLE) && !s_axis_tvalid` |
| `test_partial_last_beat` | Connect `i_valid` of `slicing_crc` to: `s_axis_tvalid ? s_axis_tkeep : '0` |
| `test_minimum_frame` | Single-beat frames have `tlast=1` on first beat. Handle in IDLE state. |
| `test_long_frame` | CRC accumulates across multiple beats. State stays in DATA until `tlast`. |
| `test_random_frames` | If specific tests pass but random tests fail, check edge cases. |
| `test_back_to_back_frames` | After `tlast`, state returns to IDLE. CRC resets when IDLE and no valid data. |

### 5.2 Key Implementation Hint

```systemverilog
// Correct instantiation of slicing_crc:
slicing_crc #(
    .SLICE_LENGTH    (DATA_NBYTES),
    .INITIAL_CRC     (32'hFFFF_FFFF),
    .INVERT_OUTPUT   (1),
    .REGISTER_OUTPUT (0)   // combinational output for same-cycle comparison
) u_rx_crc (
    .i_clk   (i_clk),
    .i_reset (crc_reset),      // Reset when IDLE and no valid data
    .i_data  (s_axis_tdata),
    .i_valid (s_axis_tvalid ? s_axis_tkeep : '0),
    .o_crc   (crc_calc)
);
```

---

## 6. Debug Workflow

### 6.1 Iterative Debugging Process

```
┌─────────────────────────────────────────────────────────────┐
│                    Agent Debug Workflow                      │
├─────────────────────────────────────────────────────────────┤
│  1. Read Specification.md                                    │
│  2. View baseline rx_mac_stream.sv                          │
│  3. View slicing_crc.sv (submodule)                         │
│  4. Implement solution                                       │
│  5. Call grade_problem() → Get reward + failed tests        │
│  6. Read DEBUG_REPORT.md for detailed hints                 │
│  7. Fix issues based on hints                               │
│  8. Repeat steps 5-7 until reward = 1.0                     │
└─────────────────────────────────────────────────────────────┘
```

### 6.2 Typical Debugging Progression

| Attempt | Score | Common Issues |
|---------|-------|---------------|
| 1 | 2/10 | Missing submodule instantiation |
| 2-3 | 4-7/10 | Wrong CRC reset timing |
| 4-5 | 7-9/10 | Single-beat frame handling |
| 6+ | 10/10 | All edge cases handled |

---

## 7. Academic Relevance

### 7.1 Related Concepts

| Concept | Description |
|---------|-------------|
| **Test-Driven Self-Debugging (TDSD)** | Agent uses test feedback to iteratively improve |
| **Simulation-Guided Iterative Refinement (SGIR)** | Simulation results guide code modifications |
| **Hierarchical Design Verification** | Testing multi-level module instantiation |

### 7.2 Research Applications

1. **RL Data Collection**: First attempt vs final result provides training signal
2. **Debugging Behavior Analysis**: Track how agents respond to different error types
3. **Hint Effectiveness**: Measure impact of different hint strategies
4. **Complexity Scaling**: Compare performance across difficulty levels

---

## 8. HUD Job Links

- **Group Size 15 Evaluation**: https://hud.ai/jobs/f6d3b591-d4ba-4193-a099-a00c84197a0d

---

## 9. Conclusions

### 9.1 Key Findings

1. **Hierarchical design is challenging**: 73.3% success rate vs ~90% for single-module problems
2. **Iterative debugging works**: All agents improved from baseline (2/10)
3. **Hint system is effective**: Test-specific hints guide agents to correct solutions
4. **Edge cases are difficult**: Single-beat frames and back-to-back frames cause most failures

### 9.2 Recommendations

1. **Provide submodule examples**: Show correct instantiation patterns
2. **Highlight timing requirements**: CRC reset timing is critical
3. **Test edge cases explicitly**: Single-beat and back-to-back frames
4. **Use combinational outputs**: `REGISTER_OUTPUT=0` for same-cycle comparison

---

*Report generated: 2024-11-30*
*Environment: HUD Framework with Claude Sonnet 4.5*

