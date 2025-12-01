import logging

from hud_controller.spec import ProblemSpec, PROBLEM_REGISTRY

logger = logging.getLogger(__name__)


PROBLEM_REGISTRY.append(
    ProblemSpec(
        id="simple_adder",
        description="""Task: Implement an 8-bit synchronous adder in sources/simple_adder.sv

Interface:
- clk: Clock signal (rising edge triggered)
- a[7:0]: First 8-bit operand  
- b[7:0]: Second 8-bit operand
- sum[7:0]: 8-bit addition result

Requirements:
On each rising clock edge, compute sum = a + b.

Implementation Steps:
1. View the file using: str_replace_based_edit_tool(command="view", path="/home/ubuntu/example-verilog-codebase/sources/simple_adder.sv")
2. Edit using: str_replace_based_edit_tool(command="str_replace", path="/home/ubuntu/example-verilog-codebase/sources/simple_adder.sv", old_str="...", new_str="...")
3. Submit when done - tests run automatically

Note: Only str_replace_based_edit_tool is available. Use it for both viewing and editing files.

See docs/Specification.md for complete details.
""",
        difficulty="easy",
        base="simple_adder_baseline",
        test="simple_adder_test",
        golden="simple_adder_golden",
        test_files=["tests/test_simple_adder_hidden.py"],
    )
)

PROBLEM_REGISTRY.append(
    ProblemSpec(
        id="simple_counter",
        description="""Task: Implement an 8-bit synchronous counter in sources/simple_counter.sv

Interface:
- clk: Clock signal (rising edge triggered)
- rst: Synchronous reset (active high)
- ena: Enable signal (count when high)
- load: Load signal (load load_value when high)
- load_value[7:0]: 8-bit value to load
- count[7:0]: 8-bit counter output

Requirements:
Priority (highest to lowest): load > rst > ena
1. When load=1: set count = load_value
2. When rst=1 and load=0: set count = 0
3. When ena=1, rst=0, load=0: increment count
4. Otherwise: maintain current count

All operations are synchronous (rising edge of clk).

Implementation Steps:
1. View the file using: str_replace_based_edit_tool(command="view", path="/home/ubuntu/example-verilog-codebase/sources/simple_counter.sv")
2. Edit using: str_replace_based_edit_tool(command="str_replace", path="/home/ubuntu/example-verilog-codebase/sources/simple_counter.sv", old_str="...", new_str="...")
3. Submit when done - tests run automatically

Note: Only str_replace_based_edit_tool is available. Use it for both viewing and editing files.
""",
        difficulty="easy",
        base="simple_counter_baseline",
        test="simple_counter_test",
        golden="simple_counter_golden",
        test_files=["tests/test_simple_counter_hidden.py"],
    )
)

PROBLEM_REGISTRY.append(
    ProblemSpec(
        id="skid_buffer",
        description="""Task: Implement a parameterized streaming buffer for AXI-Stream interfaces in sources/skid_buffer.sv

Module: skid_buffer
Parameters: DATA_WIDTH, BYPASS, DEPTH

Interface (AXI-Stream):
- Input: s_data[DATA_WIDTH-1:0], s_valid, s_ready (output)
- Output: m_data[DATA_WIDTH-1:0], m_valid (output), m_ready
- Control: clk, rst_n (active-low asynchronous reset)

Requirements:
- When BYPASS=0: Accept up to DEPTH data transfers before blocking. Output has registered latency.
- When BYPASS=1: Accept limited transfers with zero-latency passthrough when possible.
- Preserve strict ordering: output sequence must match input sequence
- Reset immediately clears all valid outputs
- Support variable DEPTH values (not hardcoded)

📖 CRITICAL: Read docs/Specification.md for complete behavioral details!

Implementation Steps:
1. Read specification: str_replace_based_edit_tool(command="view", path="/home/ubuntu/example-verilog-codebase/docs/Specification.md")
2. View baseline: str_replace_based_edit_tool(command="view", path="/home/ubuntu/example-verilog-codebase/sources/skid_buffer.sv")
3. Implement: str_replace_based_edit_tool(command="str_replace", path="/home/ubuntu/example-verilog-codebase/sources/skid_buffer.sv", old_str="...", new_str="...")
4. Test your code: grade_problem(problem_id="skid_buffer")
5. If tests fail, read debug report: str_replace_based_edit_tool(command="view", path="/home/ubuntu/example-verilog-codebase/DEBUG_REPORT.md")
6. Fix issues and repeat steps 4-5 until ALL 6 tests pass!

⚠️ IMPORTANT - ITERATION STRATEGY:
- You can call grade_problem() MULTIPLE times to test your changes
- If tests fail, a DEBUG_REPORT.md file is automatically generated with:
  • Which tests failed and why
  • Expected vs actual values
  • Specific hints on how to fix each issue
- READ THE DEBUG REPORT after each failed attempt!
- You have 150 steps available - don't give up after 1-2 attempts
- Keep iterating until reward = 1.0 (all 6 tests pass)

⚠️ DO NOT:
- Create testbenches or additional files - testing is automatic
- Give up early - partial success (e.g., 3/6 tests) means you're close!
""",
        difficulty="hard",
        base="skid_buffer_baseline",
        test="skid_buffer_test",
        golden="skid_buffer_golden",
        test_files=["tests/test_skid_buffer_hidden.py"],
    )
)
