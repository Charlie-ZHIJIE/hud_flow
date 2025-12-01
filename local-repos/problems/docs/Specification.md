# RX MAC Stream Module Specification

## 1. Overview

The `rx_mac_stream` module is an Ethernet MAC receive path component that:
1. Receives streaming data from a PHY/PCS layer via AXI-Stream interface
2. Computes CRC-32 on the payload using a `slicing_crc` submodule
3. Verifies the computed CRC against the received FCS (Frame Check Sequence)
4. Passes data through with a CRC status indicator

This is a **hierarchical design** that requires instantiating the `slicing_crc` module as a subcomponent.

## 2. Module Interface

### 2.1 Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `DATA_WIDTH` | int | 32 | Data bus width in bits (must be multiple of 8) |
| `DATA_NBYTES` | int | DATA_WIDTH/8 | Number of bytes per beat (derived) |

### 2.2 Ports

#### Clock and Reset
| Port | Direction | Width | Description |
|------|-----------|-------|-------------|
| `i_clk` | input | 1 | System clock |
| `i_reset` | input | 1 | Synchronous reset, active high |

#### Input AXI-Stream (from PHY/PCS)
| Port | Direction | Width | Description |
|------|-----------|-------|-------------|
| `s_axis_tdata` | input | DATA_WIDTH | Payload data (no preamble/SFD/FCS) |
| `s_axis_tkeep` | input | DATA_NBYTES | Byte valid mask |
| `s_axis_tvalid` | input | 1 | Data valid signal |
| `s_axis_tlast` | input | 1 | End of frame indicator |

#### FCS Sideband
| Port | Direction | Width | Description |
|------|-----------|-------|-------------|
| `i_rx_fcs` | input | 32 | Received FCS value |
| `i_rx_fcs_valid` | input | 1 | FCS valid indicator |

#### Output AXI-Stream
| Port | Direction | Width | Description |
|------|-----------|-------|-------------|
| `m_axis_tdata` | output | DATA_WIDTH | Payload data (pass-through) |
| `m_axis_tkeep` | output | DATA_NBYTES | Byte valid mask (pass-through) |
| `m_axis_tvalid` | output | 1 | Data valid signal |
| `m_axis_tlast` | output | 1 | End of frame indicator |
| `m_axis_tuser` | output | 1 | CRC status (1=OK, 0=error) |

## 3. Functional Description

### 3.1 State Machine

The module uses a simple two-state FSM:

```
        ┌─────────────────────────────────────┐
        │                                     │
        ▼                                     │
    ┌───────┐    s_axis_tvalid=1         ┌────────┐
    │ IDLE  │ ─────────────────────────► │  DATA  │
    └───────┘                            └────────┘
        ▲                                     │
        │      s_axis_tvalid=1 &&             │
        │      s_axis_tlast=1                 │
        └─────────────────────────────────────┘
```

**S_IDLE State:**
- Wait for `s_axis_tvalid` to indicate start of frame
- Output stream is idle (`m_axis_tvalid = 0`)
- CRC engine is reset

**S_DATA State:**
- Pass through input data to output
- CRC engine accumulates payload bytes
- On `tlast`: compare CRC and transition back to IDLE

### 3.2 CRC Verification

The module must instantiate `slicing_crc` as a submodule:

```systemverilog
slicing_crc #(
    .SLICE_LENGTH    (DATA_NBYTES),
    .INITIAL_CRC     (32'hFFFF_FFFF),
    .INVERT_OUTPUT   (1),
    .REGISTER_OUTPUT (0)   // combinational output for same-cycle comparison
) u_rx_crc (
    .i_clk   (i_clk),
    .i_reset (crc_reset),      // Reset when in IDLE state
    .i_data  (s_axis_tdata),
    .i_valid (...),            // Feed valid bytes based on tvalid and tkeep
    .o_crc   (crc_calc)
);
```

**Key Points:**
- `REGISTER_OUTPUT = 0` provides combinational output for same-cycle CRC comparison
- CRC reset signal should be asserted when in IDLE state (start of new frame)
- `i_valid` should be `s_axis_tkeep` when `s_axis_tvalid=1`, otherwise `0`

### 3.3 CRC Check Logic

On the last beat of a frame (`s_axis_tvalid && s_axis_tlast`):

1. If `i_rx_fcs_valid = 1`:
   - Compare computed `crc_calc` with `i_rx_fcs`
   - Set `m_axis_tuser = 1` if they match (CRC OK)
   - Set `m_axis_tuser = 0` if they don't match (CRC error)

2. If `i_rx_fcs_valid = 0`:
   - Set `m_axis_tuser = 0` (no FCS available = error)

### 3.4 Output Stream Behavior

| State | m_axis_tvalid | m_axis_tdata | m_axis_tkeep | m_axis_tlast | m_axis_tuser |
|-------|---------------|--------------|--------------|--------------|--------------|
| IDLE | 0 | 0 | 0 | 0 | 0 |
| DATA (not last) | s_axis_tvalid | s_axis_tdata | s_axis_tkeep | 0 | 0 |
| DATA (last) | s_axis_tvalid | s_axis_tdata | s_axis_tkeep | 1 | CRC result |

## 4. Timing Diagram

```
Clock    ─┬──┬──┬──┬──┬──┬──┬──┬──┬──┬──┬──┬──┬──┬──┬──┬──┬──┬──
          │  │  │  │  │  │  │  │  │  │  │  │  │  │  │  │  │  │
State     │IDLE │  DATA  │  DATA  │  DATA  │  DATA  │IDLE │
          │     │        │        │        │        │     │
s_tvalid  ──────┐████████████████████████████████████┐────────
               └────────────────────────────────────┘
s_tlast   ────────────────────────────────────┐██████┐────────
                                              └──────┘
i_rx_fcs  ────────────────────────────────────┐VALID─┐────────
                                              └──────┘
m_tvalid  ────────┐██████████████████████████████████┐────────
                 └──────────────────────────────────┘
m_tlast   ────────────────────────────────────┐██████┐────────
                                              └──────┘
m_tuser   ────────────────────────────────────┐CRC_OK┐────────
                                              └──────┘
```

## 5. Submodule: slicing_crc

The `slicing_crc` module is provided in `sources/slicing_crc.sv`. You must instantiate it correctly.

### 5.1 Interface Summary

```systemverilog
module slicing_crc #(
    parameter int SLICE_LENGTH = 8,      // Bytes per cycle
    parameter int INITIAL_CRC = 32'hFFFFFFFF,
    parameter bit INVERT_OUTPUT = 1,
    parameter bit REGISTER_OUTPUT = 1
) (
    input wire i_clk,
    input wire i_reset,
    input wire [8*SLICE_LENGTH-1:0] i_data,
    input wire [SLICE_LENGTH-1:0] i_valid,
    output wire [31:0] o_crc
);
```

### 5.2 Usage Notes

- Set `SLICE_LENGTH = DATA_NBYTES` to match the data width
- Set `REGISTER_OUTPUT = 0` for combinational CRC output (needed for same-cycle comparison)
- Set `INVERT_OUTPUT = 1` for standard Ethernet CRC
- Connect `i_reset` to reset CRC at frame start (when state is IDLE)
- Connect `i_valid` to byte enables: `s_axis_tvalid ? s_axis_tkeep : '0`

## 6. Implementation Checklist

- [ ] Define state machine enum (`S_IDLE`, `S_DATA`)
- [ ] Implement state register with reset
- [ ] Implement state transition logic
- [ ] Instantiate `slicing_crc` submodule with correct parameters
- [ ] Generate CRC reset signal (active when in IDLE)
- [ ] Connect CRC data and valid signals
- [ ] Implement CRC comparison on tlast
- [ ] Generate output stream signals
- [ ] Handle `i_rx_fcs_valid = 0` case

## 7. Test Cases

The testbench includes:

1. **test_single_frame_crc_ok** - Single frame with valid CRC
2. **test_single_frame_crc_error** - Single frame with corrupted CRC
3. **test_multiple_frames** - Multiple consecutive frames
4. **test_partial_last_beat** - Frame with partial bytes on last beat
5. **test_minimum_frame** - Minimum size frame (1 beat)
6. **test_fcs_not_valid** - Frame with i_rx_fcs_valid=0
7. **test_back_to_back_frames** - Frames with no gap between them
8. **test_various_lengths** - Frames of different lengths
9. **test_random_data** - Random payload data
10. **test_stress** - High-volume stress test

## 8. Common Mistakes

1. **Forgetting to instantiate slicing_crc** - This is a hierarchical design
2. **Wrong REGISTER_OUTPUT setting** - Must be 0 for combinational output
3. **CRC reset timing** - Reset when in IDLE, not on global reset
4. **i_valid connection** - Must gate tkeep with tvalid
5. **tuser timing** - Must be valid on the same cycle as tlast
6. **Missing FCS valid check** - Must handle i_rx_fcs_valid=0

