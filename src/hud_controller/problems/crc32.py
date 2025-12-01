"""CRC-32 problem definition."""

import logging
from hud_controller.spec import ProblemSpec, PROBLEM_REGISTRY

logger = logging.getLogger(__name__)


PROBLEM_REGISTRY.append(
    ProblemSpec(
        id="slicing_crc",
        description="""Task: Implement a CRC-32 calculator module in sources/slicing_crc.sv

The module should implement the Ethernet CRC-32 algorithm using a table-based approach
that can process multiple bytes per clock cycle.

📖 Read docs/Specification.md for the complete functional specification.

Key files:
- docs/Specification.md - Module specification and requirements
- sources/slicing_crc.sv - Implementation file (contains module skeleton)
- sources/crc_tables.mem - Precomputed lookup tables (DO NOT modify)

Testing:
- Use grade_problem(problem_id="slicing_crc") to run the test suite
- If tests fail, a DEBUG_REPORT.md will be generated with diagnostic information
- You may call grade_problem() multiple times to iterate on your solution

Notes:
- Do not create additional files or testbenches
- Do not modify the module interface (ports and parameters)
- The crc_tables.mem file contains correctly generated lookup tables
""",
        difficulty="hard",
        base="crc32_baseline",
        test="crc32_test",
        golden="crc32_golden",
        test_files=["tests/test_slicing_crc_hidden.py"],
    )
)
