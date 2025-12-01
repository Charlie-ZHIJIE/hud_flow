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
    
    # Known test patterns and their debugging hints
    TEST_HINTS = {
        "test_reset_flush": {
            "pattern": r"expected to fill (\d+), got (\d+)",
            "hint": "💡 HINT: Your buffer capacity doesn't match DEPTH parameter. "
                   "Are you using hardcoded buffer0/buffer1? You need a variable-size "
                   "memory array: `reg [DATA_WIDTH-1:0] mem [0:DEPTH-1];`"
        },
        "test_full_throughput_stream": {
            "pattern": r"Throughput|backpressure|stall",
            "hint": "💡 HINT: Check your s_ready and m_valid logic. For FIFO mode, "
                   "s_ready should be high when count < DEPTH. For bypass mode, "
                   "s_ready should be high when the skid register is empty OR m_ready is high."
        },
        "test_alternating_backpressure_preserves_order": {
            "pattern": r"order|sequence|mismatch|reorder",
            "hint": "💡 HINT: Data ordering is wrong. Check your read/write pointer logic. "
                   "For FIFO: read from mem[rd_ptr], write to mem[wr_ptr]. "
                   "Make sure pointers wrap correctly: `(ptr == DEPTH-1) ? 0 : ptr + 1`"
        },
        "test_random_handshake_stress": {
            "pattern": r"lost|duplicat|stress",
            "hint": "💡 HINT: Data is being lost or duplicated under stress. "
                   "Check simultaneous enqueue/dequeue handling (case 2'b11). "
                   "When both happen: update BOTH pointers, keep count unchanged."
        },
        "test_latency_mode": {
            "pattern": r"latency|bypass|cycle",
            "hint": "💡 HINT: Latency requirement not met. "
                   "BYPASS=1: Output should reflect input in SAME cycle when empty (0-cycle latency). "
                   "BYPASS=0: Output is always from memory (1-cycle latency minimum)."
        },
        "test_fifo_fill_drain_wrap": {
            "pattern": r"wrap|fill|drain|pointer",
            "hint": "💡 HINT: FIFO wrap-around issue. Check pointer increment logic: "
                   "`next_ptr = (ptr == DEPTH-1) ? 0 : ptr + 1;` "
                   "Also verify count updates correctly for all 4 cases of enqueue/dequeue."
        },
    }
    
    def __init__(self):
        self.last_report: Optional[DebugReport] = None
    
    def parse_test_output(self, output: str) -> list[TestFailure]:
        """Parse cocotb output to extract test failures with details."""
        failures = []
        
        # Pattern to match test failures
        # Look for AssertionError messages
        assertion_pattern = r"AssertionError:\s*(.+?)(?=\n\s*\n|\n[A-Z]|\Z)"
        
        # Look for test name and failure
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
                # Clean up the assertion message
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
                if re.search(hint_info["pattern"], output, re.IGNORECASE):
                    failure.hint = hint_info["hint"]
                else:
                    failure.hint = hint_info["hint"]  # Still provide hint
            
            failures.append(failure)
        
        return failures
    
    def generate_suggestions(self, failures: list[TestFailure], passed: int, total: int) -> list[str]:
        """Generate actionable suggestions based on failures."""
        suggestions = []
        
        # General progress message
        if passed > 0:
            suggestions.append(
                f"✅ You passed {passed}/{total} tests ({passed*100//total}%). "
                f"Keep going! You're making progress."
            )
        else:
            suggestions.append(
                "⚠️ No tests passed yet. Start by ensuring your module compiles "
                "and basic reset behavior works."
            )
        
        # Specific suggestions based on failure patterns
        reset_failed = any("reset" in f.test_name.lower() for f in failures)
        throughput_failed = any("throughput" in f.test_name.lower() for f in failures)
        order_failed = any("order" in f.test_name.lower() or "backpressure" in f.test_name.lower() for f in failures)
        stress_failed = any("stress" in f.test_name.lower() or "random" in f.test_name.lower() for f in failures)
        
        if reset_failed:
            suggestions.append(
                "🔧 FIX RESET FIRST: Ensure `rst_n` (active-low) immediately clears "
                "all valid flags and resets pointers/count to 0."
            )
        
        if throughput_failed and not reset_failed:
            suggestions.append(
                "🔧 FIX THROUGHPUT: Check your ready/valid handshake logic. "
                "s_ready should be high when buffer has space. "
                "m_valid should be high when buffer has data."
            )
        
        if order_failed:
            suggestions.append(
                "🔧 FIX ORDERING: Data must come out in the same order it went in (FIFO). "
                "Check your read/write pointer logic and memory addressing."
            )
        
        if stress_failed and not order_failed:
            suggestions.append(
                "🔧 FIX STRESS HANDLING: The tricky case is simultaneous enqueue+dequeue. "
                "Use `case ({do_dequeue, do_enqueue})` to handle all 4 combinations explicitly."
            )
        
        # Encourage iteration
        suggestions.append(
            "\n📝 NEXT STEPS:\n"
            "1. Read this debug report carefully\n"
            "2. Fix ONE issue at a time (start with reset if it's failing)\n"
            "3. Call grade_problem() again to test your changes\n"
            "4. Repeat until all 6 tests pass!"
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
        
        # Parse failures from output
        failures = self.parse_test_output(test_output)
        
        # If we have failed_tests list but no parsed failures, create basic entries
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
        
        # Generate suggestions
        suggestions = self.generate_suggestions(failures, passed, total)
        
        report = DebugReport(
            attempt_number=attempt_number,
            passed=passed,
            total=total,
            reward=reward,
            failures=failures,
            suggestions=suggestions,
            raw_output=test_output[-5000:] if len(test_output) > 5000 else test_output,  # Limit size
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
            "### How to Use This Report",
            "",
            "1. **Read the failed test analysis** above to understand what's wrong",
            "2. **Follow the hints** - they point to specific code issues",
            "3. **Fix your code** using `str_replace_based_edit_tool`",
            "4. **Test again** by calling `grade_problem(problem_id=\"skid_buffer\")`",
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

