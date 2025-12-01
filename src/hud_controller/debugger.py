#!/usr/bin/env python3
"""
Debugger module for analyzing cocotb test results and providing actionable feedback.

This module:
1. Parses cocotb test output to extract detailed error information
2. Analyzes failure patterns and provides debugging hints
3. Writes comprehensive debug reports to a fixed file for agent consumption
"""

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Fixed debug report path that agent can read
DEBUG_REPORT_PATH = "/home/ubuntu/example-verilog-codebase/DEBUG_REPORT.md"


@dataclass
class TestFailure:
    """Represents a single test failure with detailed information."""
    test_name: str
    error_type: str
    error_message: str
    expected: Optional[str] = None
    actual: Optional[str] = None
    line_info: Optional[str] = None
    hint: Optional[str] = None


@dataclass
class DebugReport:
    """Complete debug report for a grading attempt."""
    attempt_number: int
    passed: int
    total: int
    reward: float
    failures: list[TestFailure] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    raw_output: str = ""


class CocotbDebugger:
    """Analyzes cocotb test output and generates debug reports."""
    
    # Known test patterns and their debugging hints for MAC RX
    TEST_HINTS = {
        "test_reset_behavior": {
            "pattern": r"reset|initial",
            "hint": "💡 HINT: After reset, m_axis_tvalid should be 0. "
                   "State machine should be in IDLE state. "
                   "Make sure i_reset properly initializes all registers."
        },
        "test_single_frame_crc_ok": {
            "pattern": r"CRC|tuser|frame",
            "hint": "💡 HINT: Instantiate slicing_crc with REGISTER_OUTPUT=0 for "
                   "combinational CRC output. On tlast, compare crc_calc with i_rx_fcs. "
                   "Set m_axis_tuser=1 if they match."
        },
        "test_single_frame_crc_error": {
            "pattern": r"CRC error|mismatch",
            "hint": "💡 HINT: When computed CRC doesn't match i_rx_fcs, "
                   "set m_axis_tuser=0 to indicate CRC error."
        },
        "test_fcs_not_valid": {
            "pattern": r"fcs_valid|FCS",
            "hint": "💡 HINT: When i_rx_fcs_valid=0, always report CRC error "
                   "(m_axis_tuser=0) regardless of the CRC value."
        },
        "test_multiple_frames": {
            "pattern": r"multiple|consecutive|frames",
            "hint": "💡 HINT: CRC must be reset between frames. Use: "
                   "`wire crc_reset = (state == S_IDLE) && !s_axis_tvalid;`"
        },
        "test_partial_last_beat": {
            "pattern": r"partial|keep|bytes",
            "hint": "💡 HINT: Connect i_valid of slicing_crc to: "
                   "`s_axis_tvalid ? s_axis_tkeep : '0` to handle partial beats."
        },
        "test_minimum_frame": {
            "pattern": r"minimum|single beat|1 beat",
            "hint": "💡 HINT: Single-beat frames have tlast=1 on the first beat. "
                   "Handle this in IDLE state: check CRC and stay in IDLE."
        },
        "test_long_frame": {
            "pattern": r"long|64 bytes",
            "hint": "💡 HINT: CRC accumulates across multiple beats. "
                   "State must stay in DATA until tlast is seen."
        },
        "test_random_frames": {
            "pattern": r"random",
            "hint": "💡 HINT: If specific tests pass but random tests fail, "
                   "check edge cases in your state machine transitions."
        },
        "test_back_to_back_frames": {
            "pattern": r"back.to.back|no gap",
            "hint": "💡 HINT: After tlast, state returns to IDLE. "
                   "CRC resets when IDLE and no valid data. Next frame starts fresh."
        },
    }
    
    def __init__(self):
        self.last_report: Optional[DebugReport] = None
    
    def parse_test_output(self, output: str) -> list[TestFailure]:
        """Parse cocotb output to extract test failures with details."""
        failures = []
        
        # Pattern to match test failures
        assertion_pattern = r"AssertionError:\s*(.+?)(?=\n\s*\n|\n[A-Z]|\Z)"
        test_fail_pattern = r"test_(\w+).*?FAIL"
        
        # Find all failed tests
        failed_tests = re.findall(test_fail_pattern, output, re.IGNORECASE)
        
        # Find assertion errors
        assertions = re.findall(assertion_pattern, output, re.DOTALL)
        
        # Extract detailed error info
        for test_name in set(failed_tests):
            full_test_name = f"test_{test_name}"
            failure = TestFailure(
                test_name=full_test_name,
                error_type="AssertionError",
                error_message="",
            )
            
            # Try to find the specific assertion for this test
            for assertion in assertions:
                clean_msg = assertion.strip().replace('\n', ' ')[:500]
                failure.error_message = clean_msg
                
                # Try to extract expected/actual values
                expected_match = re.search(r"expected\s+(\S+)", clean_msg, re.IGNORECASE)
                actual_match = re.search(r"got\s+(\S+)", clean_msg, re.IGNORECASE)
                
                if expected_match:
                    failure.expected = expected_match.group(1)
                if actual_match:
                    failure.actual = actual_match.group(1)
                break
            
            # Add hint based on test name
            if full_test_name in self.TEST_HINTS:
                hint_info = self.TEST_HINTS[full_test_name]
                failure.hint = hint_info["hint"]
            
            failures.append(failure)
        
        return failures
    
    def generate_suggestions(self, failures: list[TestFailure], passed: int, total: int) -> list[str]:
        """Generate actionable suggestions based on failures."""
        suggestions = []
        
        if passed > 0:
            suggestions.append(
                f"✅ You passed {passed}/{total} tests ({passed*100//total}%). "
                f"Keep going! You're making progress."
            )
        else:
            suggestions.append(
                "⚠️ No tests passed yet. Make sure you have:\n"
                "  1. Instantiated the slicing_crc submodule\n"
                "  2. Implemented a state machine (IDLE, DATA)\n"
                "  3. Connected all input/output signals"
            )
        
        # Specific suggestions based on failure patterns
        reset_failed = any("reset" in f.test_name.lower() for f in failures)
        crc_failed = any("crc" in f.test_name.lower() for f in failures)
        fcs_failed = any("fcs" in f.test_name.lower() for f in failures)
        multiple_failed = any("multiple" in f.test_name.lower() for f in failures)
        
        if reset_failed:
            suggestions.append(
                "🔧 FIX RESET FIRST: Make sure i_reset initializes state to IDLE "
                "and m_axis_tvalid to 0."
            )
        
        if crc_failed and not reset_failed:
            suggestions.append(
                "🔧 FIX CRC: Check your slicing_crc instantiation. "
                "Use REGISTER_OUTPUT=0 for combinational output."
            )
        
        if fcs_failed:
            suggestions.append(
                "🔧 FIX FCS CHECK: When i_rx_fcs_valid=0, set m_axis_tuser=0."
            )
        
        if multiple_failed:
            suggestions.append(
                "🔧 FIX MULTI-FRAME: CRC must reset between frames. "
                "Use: crc_reset = (state == S_IDLE) && !s_axis_tvalid"
            )
        
        suggestions.append(
            "\n📝 NEXT STEPS:\n"
            "1. Read this debug report carefully\n"
            "2. Fix ONE issue at a time\n"
            "3. Call grade_problem() again to test your changes\n"
            "4. Repeat until all tests pass!"
        )
        
        return suggestions
    
    def create_debug_report(
        self,
        attempt_number: int,
        passed: int,
        total: int,
        reward: float,
        test_output: str,
        failed_tests: list[str],
    ) -> DebugReport:
        """Create a comprehensive debug report."""
        failures = self.parse_test_output(test_output)
        
        if not failures and failed_tests:
            for test_name in failed_tests:
                short_name = test_name.split('.')[-1] if '.' in test_name else test_name
                failure = TestFailure(
                    test_name=short_name,
                    error_type="TestFailure",
                    error_message="Test failed (see raw output for details)",
                )
                if short_name in self.TEST_HINTS:
                    failure.hint = self.TEST_HINTS[short_name]["hint"]
                failures.append(failure)
        
        suggestions = self.generate_suggestions(failures, passed, total)
        
        report = DebugReport(
            attempt_number=attempt_number,
            passed=passed,
            total=total,
            reward=reward,
            failures=failures,
            suggestions=suggestions,
            raw_output=test_output[-5000:] if len(test_output) > 5000 else test_output,
        )
        
        self.last_report = report
        return report
    
    def format_report_markdown(self, report: DebugReport) -> str:
        """Format debug report as markdown."""
        lines = [
            "# 🔍 Debug Report",
            "",
            f"## Attempt #{report.attempt_number}",
            "",
            "### Summary",
            f"- **Tests Passed**: {report.passed}/{report.total}",
            f"- **Reward**: {report.reward:.3f}",
            f"- **Status**: {'✅ ALL PASSED!' if report.passed == report.total else '❌ Some tests failed'}",
            "",
        ]
        
        if report.failures:
            lines.extend([
                "### Failed Tests Analysis",
                "",
            ])
            
            for i, failure in enumerate(report.failures, 1):
                lines.extend([
                    f"#### {i}. `{failure.test_name}`",
                    "",
                    f"**Error Type**: {failure.error_type}",
                    "",
                ])
                
                if failure.error_message:
                    lines.extend([
                        "**Error Message**:",
                        "```",
                        failure.error_message[:500],
                        "```",
                        "",
                    ])
                
                if failure.expected and failure.actual:
                    lines.extend([
                        f"**Expected**: `{failure.expected}`",
                        f"**Actual**: `{failure.actual}`",
                        "",
                    ])
                
                if failure.hint:
                    lines.extend([
                        failure.hint,
                        "",
                    ])
        
        lines.extend([
            "### Suggestions",
            "",
        ])
        
        for suggestion in report.suggestions:
            lines.append(suggestion)
            lines.append("")
        
        lines.extend([
            "---",
            "",
            "### Key Implementation Notes",
            "",
            "**This is a HIERARCHICAL DESIGN problem!**",
            "",
            "You MUST instantiate the `slicing_crc` submodule:",
            "",
            "```systemverilog",
            "slicing_crc #(",
            "    .SLICE_LENGTH    (DATA_NBYTES),",
            "    .INITIAL_CRC     (32'hFFFF_FFFF),",
            "    .INVERT_OUTPUT   (1),",
            "    .REGISTER_OUTPUT (0)",
            ") u_rx_crc (",
            "    .i_clk   (i_clk),",
            "    .i_reset (crc_reset),",
            "    .i_data  (s_axis_tdata),",
            "    .i_valid (s_axis_tvalid ? s_axis_tkeep : '0),",
            "    .o_crc   (crc_calc)",
            ");",
            "```",
            "",
            "---",
            "",
            "### How to Use This Report",
            "",
            "1. **Read the failed test analysis** above to understand what's wrong",
            "2. **Follow the hints** - they point to specific code issues",
            "3. **Fix your code** using `str_replace_based_edit_tool`",
            "4. **Test again** by calling `grade_problem(problem_id=\"rx_mac_stream\")`",
            "5. **Repeat** until all tests pass!",
            "",
            "You have plenty of steps remaining. Don't give up!",
            "",
        ])
        
        return "\n".join(lines)
    
    def write_report_to_file(self, report: DebugReport) -> str:
        """Write debug report to fixed file location."""
        markdown = self.format_report_markdown(report)
        
        try:
            Path(DEBUG_REPORT_PATH).parent.mkdir(parents=True, exist_ok=True)
            with open(DEBUG_REPORT_PATH, 'w') as f:
                f.write(markdown)
            logger.info(f"Debug report written to {DEBUG_REPORT_PATH}")
            return DEBUG_REPORT_PATH
        except Exception as e:
            logger.error(f"Failed to write debug report: {e}")
            return ""


# Global debugger instance
_debugger = CocotbDebugger()


def get_debugger() -> CocotbDebugger:
    """Get the global debugger instance."""
    return _debugger
