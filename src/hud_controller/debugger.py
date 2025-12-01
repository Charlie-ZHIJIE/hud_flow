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
    
    # Known test patterns and their debugging hints for CRC-32
    TEST_HINTS = {
        "test_reset_initial_crc": {
            "pattern": r"Reset CRC|initial",
            "hint": "💡 HINT: Check your reset logic. When i_reset=1, prev_crc should be set to INITIAL_CRC. "
                   "With INVERT_OUTPUT=1 and INITIAL_CRC=0xFFFFFFFF, output should be 0x00000000."
        },
        "test_single_byte": {
            "pattern": r"Single byte|0x",
            "hint": "💡 HINT: Check your table lookup logic for single byte. "
                   "The first 4 bytes XOR with prev_crc before lookup. "
                   "Make sure num_input_bytes is calculated correctly from i_valid."
        },
        "test_multiple_bytes_single_cycle": {
            "pattern": r"Multi-byte|multiple",
            "hint": "💡 HINT: Check parallel table lookups. Each byte uses a different table index: "
                   "`crc_tables[num_input_bytes - byte_index - 1][lookup_value]`. "
                   "All table outputs should be XORed together."
        },
        "test_full_slice": {
            "pattern": r"Full slice|8 bytes",
            "hint": "💡 HINT: For full slice (8 bytes), all 8 table lookups are needed. "
                   "Bytes 0-3 XOR with prev_crc, bytes 4-7 are direct lookups."
        },
        "test_multi_cycle_stream": {
            "pattern": r"Multi-cycle|stream|16 bytes",
            "hint": "💡 HINT: CRC state must persist across cycles. Check that prev_crc is updated "
                   "with crc_calc when any_valid is high. The running CRC accumulates correctly."
        },
        "test_ethernet_frame": {
            "pattern": r"Ethernet|frame",
            "hint": "💡 HINT: This tests realistic Ethernet data. If other tests pass but this fails, "
                   "check byte ordering. LSB of i_data is byte 0."
        },
        "test_partial_slices": {
            "pattern": r"Partial slice|varying",
            "hint": "💡 HINT: For partial slices (< 4 bytes), you need to XOR in remaining bytes of prev_crc: "
                   "`crc_calc = crc_calc ^ (prev_crc >> (8*num_input_bytes))`"
        },
        "test_consecutive_packets": {
            "pattern": r"consecutive|packets|reset between",
            "hint": "💡 HINT: Each packet should start with fresh CRC. "
                   "Make sure reset properly clears state between packets."
        },
        "test_random_vectors": {
            "pattern": r"Random test|random",
            "hint": "💡 HINT: Random vector tests verify general correctness. If specific tests pass "
                   "but random tests fail, check edge cases in your implementation."
        },
        "test_long_packet": {
            "pattern": r"Long packet|256 bytes",
            "hint": "💡 HINT: Long packet test verifies CRC accumulation over many cycles. "
                   "Ensure prev_crc state persists correctly across all cycles."
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
                
                # Try to extract expected/actual CRC values
                expected_match = re.search(r"expected\s+0x([0-9A-Fa-f]+)", clean_msg, re.IGNORECASE)
                actual_match = re.search(r"got\s+0x([0-9A-Fa-f]+)", clean_msg, re.IGNORECASE)
                
                if expected_match:
                    failure.expected = f"0x{expected_match.group(1)}"
                if actual_match:
                    failure.actual = f"0x{actual_match.group(1)}"
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
                "⚠️ No tests passed yet. Start by ensuring your module compiles "
                "and the CRC tables are loaded correctly."
            )
        
        # Specific suggestions based on failure patterns
        reset_failed = any("reset" in f.test_name.lower() for f in failures)
        single_failed = any("single" in f.test_name.lower() for f in failures)
        multi_failed = any("multi" in f.test_name.lower() for f in failures)
        partial_failed = any("partial" in f.test_name.lower() for f in failures)
        
        if reset_failed:
            suggestions.append(
                "🔧 FIX RESET FIRST: Ensure i_reset sets prev_crc to INITIAL_CRC."
            )
        
        if single_failed and not reset_failed:
            suggestions.append(
                "🔧 FIX SINGLE BYTE: Check num_input_bytes calculation and table indexing."
            )
        
        if multi_failed and not single_failed:
            suggestions.append(
                "🔧 FIX MULTI-BYTE: Ensure all valid bytes contribute to CRC via XOR."
            )
        
        if partial_failed:
            suggestions.append(
                "🔧 FIX PARTIAL SLICES: Remember to XOR in remaining prev_crc bytes "
                "when processing fewer than 4 bytes."
            )
        
        suggestions.append(
            "\n📝 NEXT STEPS:\n"
            "1. Read this debug report carefully\n"
            "2. Fix ONE issue at a time (start with reset if it's failing)\n"
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
                        f"**Expected CRC**: `{failure.expected}`",
                        f"**Actual CRC**: `{failure.actual}`",
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
            "### How to Use This Report",
            "",
            "1. **Read the failed test analysis** above to understand what's wrong",
            "2. **Follow the hints** - they point to specific code issues",
            "3. **Fix your code** using `str_replace_based_edit_tool`",
            "4. **Test again** by calling `grade_problem(problem_id=\"slicing_crc\")`",
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

