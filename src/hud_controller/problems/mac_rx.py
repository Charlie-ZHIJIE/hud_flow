"""MAC RX Stream problem definition."""

MAC_RX_PROBLEM = {
    "id": "rx_mac_stream",
    "name": "RX MAC Stream with CRC Verification",
    "difficulty": "Advanced",
    "description": """Implement an Ethernet MAC receive path component that:
1. Receives streaming data via AXI-Stream interface
2. Instantiates the slicing_crc submodule to compute CRC-32
3. Verifies computed CRC against received FCS (Frame Check Sequence)
4. Reports CRC status via m_axis_tuser (1=OK, 0=error)

This is a HIERARCHICAL DESIGN problem - you must correctly instantiate
the provided slicing_crc module as a subcomponent.""",
    
    "module": "rx_mac_stream",
    "source_file": "sources/rx_mac_stream.sv",
    "test_file": "tests/test_rx_mac_stream_hidden.py",
    "spec_file": "docs/Specification.md",
    
    "provided_files": [
        "sources/slicing_crc.sv",    # Submodule - DO NOT MODIFY
        "sources/crc_tables.mem",     # CRC lookup tables
    ],
    
    "parameters": {
        "DATA_WIDTH": 32,
        "DATA_NBYTES": 4,
    },
    
    "interface": {
        "inputs": [
            "i_clk",
            "i_reset",
            "s_axis_tdata[DATA_WIDTH-1:0]",
            "s_axis_tkeep[DATA_NBYTES-1:0]",
            "s_axis_tvalid",
            "s_axis_tlast",
            "i_rx_fcs[31:0]",
            "i_rx_fcs_valid",
        ],
        "outputs": [
            "m_axis_tdata[DATA_WIDTH-1:0]",
            "m_axis_tkeep[DATA_NBYTES-1:0]",
            "m_axis_tvalid",
            "m_axis_tlast",
            "m_axis_tuser",
        ],
    },
    
    "requirements": [
        "Implement a 2-state FSM (IDLE, DATA)",
        "Instantiate slicing_crc with correct parameters",
        "Pass through AXI-Stream signals from input to output",
        "Compare computed CRC with i_rx_fcs on tlast",
        "Set m_axis_tuser=1 if CRC matches, 0 otherwise",
        "Handle i_rx_fcs_valid=0 case (report error)",
    ],
    
    "hints": {
        "test_reset_behavior": 
            "💡 HINT: After reset, m_axis_tvalid should be 0. "
            "State machine should be in IDLE state.",
            
        "test_single_frame_crc_ok":
            "💡 HINT: Instantiate slicing_crc with REGISTER_OUTPUT=0 for "
            "combinational CRC output. Compare crc_calc with i_rx_fcs on tlast.",
            
        "test_single_frame_crc_error":
            "💡 HINT: When computed CRC doesn't match i_rx_fcs, "
            "set m_axis_tuser=0 to indicate CRC error.",
            
        "test_fcs_not_valid":
            "💡 HINT: When i_rx_fcs_valid=0, always report CRC error "
            "(m_axis_tuser=0) regardless of CRC value.",
            
        "test_multiple_frames":
            "💡 HINT: CRC must be reset between frames. Use crc_reset signal "
            "that is active when state==IDLE && !s_axis_tvalid.",
            
        "test_partial_last_beat":
            "💡 HINT: Connect i_valid of slicing_crc to: "
            "s_axis_tvalid ? s_axis_tkeep : '0",
            
        "test_minimum_frame":
            "💡 HINT: Single-beat frames (tlast on first beat) need special "
            "handling in IDLE state. Check CRC and return to IDLE.",
            
        "test_long_frame":
            "💡 HINT: CRC accumulates across multiple beats. Make sure "
            "state stays in DATA until tlast is seen.",
            
        "test_random_frames":
            "💡 HINT: If specific tests pass but random tests fail, "
            "check edge cases in your state machine transitions.",
            
        "test_back_to_back_frames":
            "💡 HINT: After tlast, state returns to IDLE. CRC resets when "
            "IDLE and no valid data. Next frame starts fresh.",
    },
    
    "slicing_crc_instantiation": """
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
""",
    
    "total_tests": 10,
}

