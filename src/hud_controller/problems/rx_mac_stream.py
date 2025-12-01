"""
MAC RX Stream problem definition for HUD evaluation.
"""

from hud_controller.spec import PROBLEM_REGISTRY, ProblemSpec, HintSpec


# Problem description with implementation guidance
PROBLEM_DESCRIPTION = """Task: Implement an Ethernet MAC receive path component in sources/rx_mac_stream.sv

Module: rx_mac_stream

**THIS IS A HIERARCHICAL DESIGN PROBLEM**
You must instantiate the provided `slicing_crc` submodule to compute CRC-32.

Parameters:
- DATA_WIDTH (default: 32)
- DATA_NBYTES (localparam: DATA_WIDTH/8)

Interface:
- Input Clock/Reset: i_clk, i_reset
- AXI-Stream Input: s_axis_tdata, s_axis_tkeep, s_axis_tvalid, s_axis_tlast
- FCS Sideband: i_rx_fcs[31:0], i_rx_fcs_valid
- AXI-Stream Output: m_axis_tdata, m_axis_tkeep, m_axis_tvalid, m_axis_tlast, m_axis_tuser

Requirements:
1. Implement a 2-state FSM (IDLE, DATA)
2. Pass through AXI-Stream signals from input to output
3. Instantiate slicing_crc to compute CRC-32 on the data stream
4. Compare computed CRC with i_rx_fcs when tlast is asserted
5. Set m_axis_tuser=1 if CRC matches, 0 otherwise
6. Handle i_rx_fcs_valid=0 case (always report error)
7. Reset CRC between frames (when IDLE and no valid data)

📖 CRITICAL: Read docs/Specification.md for complete behavioral details!

Implementation Steps:
1. Read specification: str_replace_based_edit_tool(command="view", path="/home/ubuntu/example-verilog-codebase/docs/Specification.md")
2. View baseline: str_replace_based_edit_tool(command="view", path="/home/ubuntu/example-verilog-codebase/sources/rx_mac_stream.sv")
3. View slicing_crc submodule: str_replace_based_edit_tool(command="view", path="/home/ubuntu/example-verilog-codebase/sources/slicing_crc.sv")
4. Implement: str_replace_based_edit_tool(command="str_replace", path="...", old_str="...", new_str="...")
5. Test your code: grade_problem(problem_id="rx_mac_stream")
6. If tests fail, read debug report: str_replace_based_edit_tool(command="view", path="/home/ubuntu/example-verilog-codebase/DEBUG_REPORT.md")
7. Fix issues and repeat steps 5-6 until ALL tests pass!

⚠️ IMPORTANT - ITERATION STRATEGY:
- You can call grade_problem() MULTIPLE times to test your changes
- If tests fail, a DEBUG_REPORT.md file is automatically generated with:
  • Which tests failed and why
  • Expected vs actual values
  • Specific hints on how to fix each issue
- READ THE DEBUG REPORT after each failed attempt!
- You have 150 steps available - don't give up after 1-2 attempts
- Keep iterating until reward = 1.0 (all tests pass)

⚠️ DO NOT:
- Create testbenches or additional files - testing is automatic
- Modify slicing_crc.sv or crc_tables.mem - they are provided and correct
- Give up early - partial success means you're close!
"""


# Hints for the problem
HINTS = [
    HintSpec(
        hint_type="legit",
        text="Instantiate slicing_crc with REGISTER_OUTPUT=0 for combinational CRC output that can be compared in the same cycle as tlast.",
        why_legitmate="Guides correct submodule instantiation without revealing implementation details.",
    ),
    HintSpec(
        hint_type="legit",
        text="CRC reset signal should be: (state == S_IDLE) && !s_axis_tvalid. This ensures CRC is not reset when first data beat arrives.",
        why_legitmate="Common timing issue that causes CRC mismatch on first frame.",
    ),
    HintSpec(
        hint_type="legit",
        text="Connect slicing_crc i_valid to: s_axis_tvalid ? s_axis_tkeep : '0 to handle partial beats correctly.",
        why_legitmate="Standard pattern for AXI-Stream to CRC connection.",
    ),
    HintSpec(
        hint_type="legit",
        text="Single-beat frames (tlast=1 on first beat) need special handling in IDLE state - check CRC and stay in IDLE.",
        why_legitmate="Edge case that is easy to miss.",
    ),
]


# Register the problem
MAC_RX_PROBLEM = ProblemSpec(
    id="rx_mac_stream",
    description=PROBLEM_DESCRIPTION,
    base="baseline",
    test="test",
    golden="golden",
    test_files=["tests/test_rx_mac_stream_hidden.py"],
    hints=HINTS,
    difficulty="advanced",
    task_type="coding",
    review_level="no-review",
    startup_command="hud_eval",
    demo=False,
    too_hard=False,
    debug_report_path="/home/ubuntu/example-verilog-codebase/DEBUG_REPORT.md",
)

PROBLEM_REGISTRY.append(MAC_RX_PROBLEM)

