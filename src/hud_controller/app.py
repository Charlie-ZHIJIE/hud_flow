#!/usr/bin/env python3
"""
MCP Server application for CRC-32 problem evaluation.
"""

import asyncio
import logging
import os

import click
from mcp.server.fastmcp import FastMCP
from mcp.types import ImageContent, TextContent
from pydantic import Field

import hud_controller.problems
from hud_controller.grading_runner import GradingRunner
from hud_controller.utils import import_submodules
from hud_controller.debugger import get_debugger, DEBUG_REPORT_PATH

from .setup import start_dinit
from .spec import PROBLEM_REGISTRY, Grade, ProblemSpec
from .tools.base import ToolResult

logger = logging.getLogger(__name__)

# MCP server name
mcp = FastMCP("crc32_evaluation", log_level="DEBUG", debug=True)

TEST_MODE = os.environ.get("MCP_TESTING_MODE", "1") in ["1", "true"]

if TEST_MODE:
    from .tools.bash import BashTool
    from .tools.edit import Command, EditTool

    edit_tool = EditTool()
    bash_tool = BashTool()

    @mcp.tool(
        name="str_replace_based_edit_tool",
        description="Create and edit files using str_replace_based_edit_tool. Please use absolute paths for all file names.",
    )
    async def str_replace_based_edit_tool(
        *,
        command: Command,
        path: str,
        file_text: str | None = None,
        view_range: list[int] | None = None,
        old_str: str | None = None,
        new_str: str | None = None,
        insert_line: int | None = None,
    ) -> ToolResult:
        """Edit or create files using string replacement operations."""
        return await edit_tool(
            command=command,
            path=path,
            file_text=file_text,
            view_range=view_range,
            old_str=old_str,
            new_str=new_str,
            insert_line=insert_line,
        )

    @mcp.tool(
        name="bash",
        description="Run bash commands. If you need to restart the bash session, set restart to true.",
    )
    async def bash(*, command: str | None = None, restart: bool = False) -> ToolResult:
        return await bash_tool(
            command=command,
            restart=restart,
        )


# Import all problem modules to ensure problems are registered
import_submodules(hud_controller.problems)


# Template for problem statement
template = """
You will be working on a task for example-verilog-codebase.
The repository has already been cloned in the environment in /home/ubuntu/example-verilog-codebase.
Iverilog and Verilator have been installed.
Do not change any of the input or output ports of the modules.

You should write verilog testbenches to test your code and ensure it matches the functional specification (in addition to syntactic correctness).

Use the tools provided to complete the following task:

<STATEMENT>
"""


def spec_to_statement(spec: ProblemSpec) -> str:
    """Convert a problem spec to a statement."""
    hints_enabled = os.environ.get("HINTS", "none").lower() in ["all"]
    statement = spec.description
    
    if hints_enabled and len(spec.hints) > 0:
        hint_text = ""
        for hint_spec in spec.hints:
            hint_text += f"\n - {hint_spec.text}\n"
        statement += "\n\n" + f"<HINTS>{hint_text}</HINTS>"
    return template.replace("<STATEMENT>", statement)


def _get_spec(problem_id: str) -> ProblemSpec:
    """Helper to lookup a problem spec by id."""
    for spec in PROBLEM_REGISTRY:
        if spec.id == problem_id:
            return spec
    raise ValueError(f"No problem found for id: {problem_id}")


@mcp.tool()
async def setup_problem(
    problem_id: str = Field(description="The id of the problem to solve"),
) -> str:
    """Starts the environment and returns the problem statement."""
    spec = _get_spec(problem_id)

    logger.info(f"=== SETUP_PROBLEM DEBUG ===")
    logger.info(f"Problem ID: {problem_id}")
    logger.info(f"Spec: {spec}")

    await start_dinit()
    return spec_to_statement(spec)


# Global tracker for grading attempts
_grading_attempts = {}
_last_test_output = {}
_last_grade = {}


@mcp.tool()
async def grade_problem(
    problem_id: str,
    transcript: str | int = Field(description="The entire transcript produced by the model and its tool calls"),
    reward_mode: str = "fine_grained",
) -> dict:
    """
    Test your solution and get grading results.
    
    This tool runs the hidden test suite against your implementation and returns:
    - How many tests passed/failed
    - Which specific tests failed
    - A debug report is written to DEBUG_REPORT.md with detailed analysis
    
    IMPORTANT: If tests fail, you MUST read the debug report to understand what went wrong:
    str_replace_based_edit_tool(command="view", path="/home/ubuntu/example-verilog-codebase/DEBUG_REPORT.md")
    """
    global _grading_attempts, _last_test_output, _last_grade
    
    session_key = f"{problem_id}_{os.getpid()}"
    
    spec = _get_spec(problem_id)
    runner = GradingRunner(
        base=spec.base,
        test=spec.test,
        golden=spec.golden,
        test_files=spec.test_files,
        reward_mode=reward_mode,
    )

    reward, result = runner.run_grading()
    
    # Track grading attempts
    if session_key not in _grading_attempts:
        _grading_attempts[session_key] = []
    
    attempt_num = len(_grading_attempts[session_key]) + 1
    attempt_data = {
        'attempt': attempt_num,
        'reward': reward,
        'passed': result.get('passed', 0),
        'total': result.get('total', 0),
        'failed_tests': result.get('failed_tests', []),
    }
    _grading_attempts[session_key].append(attempt_data)
    
    _last_test_output[session_key] = result.get('test_output', '')
    
    # Add benchmark data
    result['attempt_number'] = attempt_num
    result['first_attempt_reward'] = _grading_attempts[session_key][0]['reward']
    result['first_attempt_passed'] = _grading_attempts[session_key][0]['passed']
    result['first_attempt_total'] = _grading_attempts[session_key][0]['total']
    result['all_attempts'] = _grading_attempts[session_key].copy()
    
    # Log benchmark info
    if attempt_num == 1:
        logger.info(f"📊 FIRST ATTEMPT (Benchmark): {reward:.3f} ({result.get('passed', 0)}/{result.get('total', 0)} tests)")
    else:
        first_reward = _grading_attempts[session_key][0]['reward']
        improvement = reward - first_reward
        logger.info(f"📈 Attempt #{attempt_num}: {reward:.3f} ({result.get('passed', 0)}/{result.get('total', 0)} tests) | First: {first_reward:.3f} | Δ: {improvement:+.3f}")
    
    # Generate debug report if tests failed
    if reward < 1.0:
        debugger = get_debugger()
        debug_report = debugger.create_debug_report(
            attempt_number=attempt_num,
            passed=result.get('passed', 0),
            total=result.get('total', 8),
            reward=reward,
            test_output=result.get('test_output', ''),
            failed_tests=result.get('failed_tests', []),
        )
        report_path = debugger.write_report_to_file(debug_report)
        result['debug_report_path'] = report_path
        logger.info(f"📝 Debug report written to {report_path}")
    
    # Build response message
    passed = result.get('passed', 0)
    total = result.get('total', 8)
    failed_tests = result.get('failed_tests', [])
    
    # Store Grade for evaluate_problem
    _last_grade[session_key] = Grade(
        subscores={"Tests": reward},
        weights={"Tests": 1.0},
        metadata=result,
    )
    
    if reward >= 1.0:
        message = f"""✅ SUCCESS! All {total} tests passed!

🎉 Congratulations! Your implementation is correct.
Reward: {reward:.3f} (100%)

You have completed the task successfully."""
    else:
        failed_list = "\n".join([f"  - {t}" for t in failed_tests]) if failed_tests else "  (unknown)"
        
        message = f"""❌ TESTS FAILED: {passed}/{total} passed ({reward*100:.0f}%)

Failed tests:
{failed_list}

🔧 DEBUG WORKFLOW - FOLLOW THESE STEPS:

STEP 1: Read the debug report NOW:
   str_replace_based_edit_tool(command="view", path="{DEBUG_REPORT_PATH}")

STEP 2: The debug report tells you:
   - WHY each test failed (exact error messages)
   - WHAT CRC values were expected vs actual
   - HOW to fix each specific issue

STEP 3: Fix your code based on the hints in the debug report

STEP 4: Call grade_problem() again to verify your fix

⚠️ IMPORTANT: You MUST read {DEBUG_REPORT_PATH} before trying to fix anything!
The debug report contains specific hints that will help you fix the issues quickly."""
    
    # Return dict with reward for HUD framework to parse
    return {
        "reward": reward,
        "subscores": {"Tests": reward},
        "weights": {"Tests": 1.0},
        "passed": passed,
        "total": total,
        "message": message,
    }


@mcp.tool()
async def evaluate_problem(
    problem_id: str,
    transcript: str | int = Field(description="The entire transcript produced by the model and its tool calls"),
    reward_mode: str = "fine_grained",
) -> Grade:
    """
    Final evaluation tool called by HUD framework.
    Returns the Grade object from the last grade_problem call.
    """
    global _last_grade
    
    session_key = f"{problem_id}_{os.getpid()}"
    
    if session_key in _last_grade:
        return _last_grade[session_key]
    
    spec = _get_spec(problem_id)
    runner = GradingRunner(
        base=spec.base,
        test=spec.test,
        golden=spec.golden,
        test_files=spec.test_files,
        reward_mode=reward_mode,
    )
    
    reward, result = runner.run_grading()
    
    return Grade(
        subscores={"Tests": reward},
        weights={"Tests": 1.0},
        metadata=result,
    )


@mcp.tool()
async def debug_test_results(
    problem_id: str = Field(description="The problem ID to debug"),
) -> str:
    """
    Get detailed debugging information for the last test run.
    """
    global _grading_attempts, _last_test_output
    
    session_key = f"{problem_id}_{os.getpid()}"
    
    if session_key not in _grading_attempts or not _grading_attempts[session_key]:
        return (
            "❌ No grading attempts found for this problem.\n\n"
            f"Please call grade_problem(problem_id=\"{problem_id}\") first to run the tests, "
            "then call debug_test_results() to analyze the results."
        )
    
    last_attempt = _grading_attempts[session_key][-1]
    test_output = _last_test_output.get(session_key, '')
    
    if last_attempt['reward'] >= 1.0:
        return (
            "✅ All tests passed! No debugging needed.\n\n"
            f"Your solution achieved {last_attempt['passed']}/{last_attempt['total']} tests.\n"
            "Congratulations!"
        )
    
    debugger = get_debugger()
    debug_report = debugger.create_debug_report(
        attempt_number=last_attempt['attempt'],
        passed=last_attempt['passed'],
        total=last_attempt['total'],
        reward=last_attempt['reward'],
        test_output=test_output,
        failed_tests=last_attempt['failed_tests'],
    )
    
    report_path = debugger.write_report_to_file(debug_report)
    report_text = debugger.format_report_markdown(debug_report)
    
    report_text += f"\n\n---\n📁 This report has also been saved to: `{report_path}`\n"
    report_text += f"You can read it anytime using: `str_replace_based_edit_tool(command=\"view\", path=\"{report_path}\")`\n"
    
    return report_text


@click.command()
@click.argument("problem_id")
def setup_problem_script(problem_id: str):
    """Set up a problem environment and return the problem statement."""
    statement = asyncio.run(setup_problem(problem_id))
    print(statement)


@click.command()
def main():
    """Run the MCP server."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
