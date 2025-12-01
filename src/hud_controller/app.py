import asyncio
import logging
import os

import click
from mcp.server.fastmcp import FastMCP  # type: ignore
from mcp.types import ImageContent, TextContent  # type: ignore
from pydantic import Field

import hud_controller.problems
from hud_controller.grading_runner import GradingRunner
from hud_controller.utils import import_submodules
from hud_controller.debugger import get_debugger, DEBUG_REPORT_PATH

from .setup import start_dinit
from .spec import PROBLEM_REGISTRY, Grade, ProblemSpec
from .tools.base import ToolResult

logger = logging.getLogger(__name__)

# [CUSTOMIZE] Set your MCP server name
mcp = FastMCP("agent_evaluation", log_level="DEBUG", debug=True)

TEST_MODE = os.environ.get("MCP_TESTING_MODE", "1") in ["1", "true"]

if TEST_MODE:
    # Note, these tools are only available in testing mode for the purpose of testing
    # If the enviroment performs well with these tools, it will also work with our internal
    # implementation

    from .tools.bash import BashTool
    from .tools.edit import Command, EditTool

    edit_tool = EditTool()
    bash_tool = BashTool()

    @mcp.tool(
        name="str_replace_based_edit_tool",
        description="Create and edit files using str_replace_based_edit_tool.  Please use absolute paths for all file names.",
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
        """Edit or create files using string replacement operations.

        Args:
            command (Command): The edit command to perform (e.g., create, edit, view)
            path (str): Absolute path to the target file
            file_text (str | None, optional): Content to write when creating a new file. Defaults to None.
            view_range (list[int] | None, optional): Line range to view [start, end]. Defaults to None.
            old_str (str | None, optional): String to replace when editing. Defaults to None.
            new_str (str | None, optional): Replacement string when editing. Defaults to None.
            insert_line (int | None, optional): Line number for insertion. Defaults to None.

        Returns:
            ToolResult: Result of the edit operation
        """
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

# import all submodules
# Import all problem modules to ensure problems are registered
import_submodules(hud_controller.problems)


# [CUSTOMIZE] Update this template for your project
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
    """
    Convert a problem spec to a statement.
    """
    hints_enabled = os.environ.get("HINTS", "none").lower() in ["all"]
    statement = spec.description
    
    if hints_enabled and len(spec.hints) > 0:
        hint_text = ""
        for hint_spec in spec.hints:
            hint_text += f"\n - {hint_spec.text}\n"
        statement += "\n\n" + f"<HINTS>{hint_text}</HINTS>"
    return template.replace("<STATEMENT>", statement)


# helper to lookup a problem spec by id
def _get_spec(problem_id: str) -> ProblemSpec:
    for spec in PROBLEM_REGISTRY:
        if spec.id == problem_id:
            return spec
    raise ValueError(f"No problem found for id: {problem_id}")


# Implementation notes: setup_problem will only be called once per enviroment instance
@mcp.tool()
async def setup_problem(
    problem_id: str = Field(description="The id of the problem to solve"),
) -> str:
    """Starts the enviroment and returns the problem statement"""
    spec = _get_spec(problem_id)

    logger.info(f"=== SETUP_PROBLEM DEBUG ===")
    logger.info(f"Problem ID: {problem_id}")
    logger.info(f"Spec: {spec}")

    # Start the dinit services
    await start_dinit()
    # create the full statement
    return spec_to_statement(spec)


@click.command()
@click.argument("problem_id")
def setup_problem_script(problem_id: str):
    """Set up a problem environment and return the problem statement."""
    statement = asyncio.run(setup_problem(problem_id))
    print(statement)


# Global tracker for grading attempts (for benchmark data collection)
_grading_attempts = {}
# Global storage for last test output (for debugger)
_last_test_output = {}

# Implementation note: grade_problem CAN be called multiple times in fine_grained mode for iteration
@mcp.tool()
async def grade_problem(
    problem_id: str,
    transcript: str | int = Field(description="The entire transcript produced by the model and its tool calls"),
    reward_mode: str = "fine_grained",  # "binary" or "fine_grained"
) -> str:
    """
    Test your solution and get grading results.
    
    This tool runs the hidden test suite against your implementation and returns:
    - How many tests passed/failed
    - Which specific tests failed
    - A debug report is written to DEBUG_REPORT.md with detailed analysis
    
    IMPORTANT: If tests fail, you MUST read the debug report to understand what went wrong:
    str_replace_based_edit_tool(command="view", path="/home/ubuntu/example-verilog-codebase/DEBUG_REPORT.md")
    
    Args:
        problem_id: The problem to grade
        transcript: The entire transcript produced by the model
        reward_mode: "binary" (0/1) or "fine_grained" (0.0-1.0 based on passed/total)
    
    Returns:
        A string with test results and instructions for next steps
    """
    
    global _grading_attempts, _last_test_output
    
    # Get unique session ID (use problem_id as key since each episode has one problem)
    session_key = f"{problem_id}_{os.getpid()}"
    
    spec = _get_spec(problem_id)
    runner = GradingRunner(
        base=spec.base,
        test=spec.test,
        golden=spec.golden,
        test_files=spec.test_files,
        reward_mode=reward_mode,  # Pass reward_mode to runner
    )

    reward, result = runner.run_grading()  # Returns float reward (0.0-1.0)
    
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
    
    # Store test output for debugger
    _last_test_output[session_key] = result.get('test_output', '')
    
    # Add benchmark data to metadata
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
    debug_report_generated = False
    if reward < 1.0:
        debugger = get_debugger()
        debug_report = debugger.create_debug_report(
            attempt_number=attempt_num,
            passed=result.get('passed', 0),
            total=result.get('total', 6),
            reward=reward,
            test_output=result.get('test_output', ''),
            failed_tests=result.get('failed_tests', []),
        )
        report_path = debugger.write_report_to_file(debug_report)
        result['debug_report_path'] = report_path
        debug_report_generated = True
        logger.info(f"📝 Debug report written to {report_path}")
    
    # Log results based on reward mode
    mode = result.get('reward_mode', reward_mode)
    if mode == "binary":
        if reward >= 1.0:
            logger.info(f"Grading successful! Reward (binary): {reward:.1f}")
        else:
            logger.error(f"Grading failed! Reward (binary): {reward:.1f}")
    else:  # fine_grained
        if reward >= 1.0:
            logger.info(f"Grading successful! Reward (fine-grained): {reward:.3f}")
        elif reward > 0.0:
            logger.info(f"Partial success. Reward (fine-grained): {reward:.3f} ({result.get('passed', 0)}/{result.get('total', 6)} tests passed)")
        else:
            logger.error(f"Grading failed! Reward (fine-grained): {reward:.3f}")

    # Build response message that agent can see
    passed = result.get('passed', 0)
    total = result.get('total', 6)
    failed_tests = result.get('failed_tests', [])
    
    if reward >= 1.0:
        # All tests passed!
        response = f"""
✅ SUCCESS! All {total} tests passed!

🎉 Congratulations! Your implementation is correct.
Reward: {reward:.3f} (100%)

You have completed the task successfully.
"""
    else:
        # Some tests failed - provide clear instructions
        failed_list = "\n".join([f"  - {t}" for t in failed_tests]) if failed_tests else "  (unknown)"
        
        response = f"""
❌ TESTS FAILED: {passed}/{total} passed ({reward*100:.0f}%)

Failed tests:
{failed_list}

🔧 DEBUG WORKFLOW - FOLLOW THESE STEPS:

STEP 1: Read the debug report NOW:
   str_replace_based_edit_tool(command="view", path="{DEBUG_REPORT_PATH}")

STEP 2: The debug report tells you:
   - WHY each test failed (exact error messages)
   - WHAT values were expected vs actual
   - HOW to fix each specific issue

STEP 3: Fix your code based on the hints in the debug report

STEP 4: Call grade_problem() again to verify your fix

⚠️ IMPORTANT: You MUST read {DEBUG_REPORT_PATH} before trying to fix anything!
The debug report contains specific hints that will help you fix the issues quickly.
"""
    
    # Store the Grade object for evaluate_problem to retrieve
    global _last_grade
    _last_grade[session_key] = Grade(
        subscores={"Tests": reward},
        weights={"Tests": 1.0},
        metadata=result,
    )
    
    return response


# Store last grade for evaluate_problem
_last_grade = {}

# This is the tool that HUD framework calls for final evaluation
@mcp.tool()
async def evaluate_problem(
    problem_id: str,
    transcript: str | int = Field(description="The entire transcript produced by the model and its tool calls"),
    reward_mode: str = "fine_grained",
) -> Grade:
    """
    Final evaluation tool called by HUD framework.
    Returns the Grade object from the last grade_problem call.
    
    Note: This is typically called automatically by HUD at the end of an episode.
    Agents should use grade_problem() instead for testing their solutions.
    """
    global _last_grade
    
    session_key = f"{problem_id}_{os.getpid()}"
    
    # If we have a cached grade, return it
    if session_key in _last_grade:
        return _last_grade[session_key]
    
    # Otherwise, run grading and return Grade
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
    
    This tool analyzes the cocotb test output and provides:
    - Which specific tests failed and why
    - Expected vs actual values
    - Hints on how to fix each failure
    - Suggested next steps
    
    The debug report is also saved to: /home/ubuntu/example-verilog-codebase/DEBUG_REPORT.md
    
    Call this after grade_problem() returns a partial score to understand what went wrong.
    
    Args:
        problem_id: The problem to debug
    
    Returns:
        Detailed debug report with analysis and hints
    """
    global _grading_attempts, _last_test_output
    
    session_key = f"{problem_id}_{os.getpid()}"
    
    # Check if we have any grading attempts
    if session_key not in _grading_attempts or not _grading_attempts[session_key]:
        return (
            "❌ No grading attempts found for this problem.\n\n"
            "Please call grade_problem(problem_id=\"{}\") first to run the tests, "
            "then call debug_test_results() to analyze the results.".format(problem_id)
        )
    
    # Get the last attempt data
    last_attempt = _grading_attempts[session_key][-1]
    test_output = _last_test_output.get(session_key, '')
    
    # If all tests passed, no debugging needed
    if last_attempt['reward'] >= 1.0:
        return (
            "✅ All tests passed! No debugging needed.\n\n"
            f"Your solution achieved {last_attempt['passed']}/{last_attempt['total']} tests.\n"
            "Congratulations!"
        )
    
    # Generate debug report
    debugger = get_debugger()
    debug_report = debugger.create_debug_report(
        attempt_number=last_attempt['attempt'],
        passed=last_attempt['passed'],
        total=last_attempt['total'],
        reward=last_attempt['reward'],
        test_output=test_output,
        failed_tests=last_attempt['failed_tests'],
    )
    
    # Write to file
    report_path = debugger.write_report_to_file(debug_report)
    
    # Format as string response
    report_text = debugger.format_report_markdown(debug_report)
    
    # Add file location reminder
    report_text += f"\n\n---\n📁 This report has also been saved to: `{report_path}`\n"
    report_text += "You can read it anytime using: `str_replace_based_edit_tool(command=\"view\", path=\"{}\")`\n".format(report_path)
    
    return report_text


@click.command()
@click.argument("problem_id", envvar="PROBLEM_ID")
@click.option("--only-server", is_flag=True, help="Only start the server and wait for it to be ready")
@click.option("--output_path", default="/tmp/grade_junit.xml", help="Path to output the JUNIT XML file")
def grade_problem_script(
    problem_id: str,
    output_path: str = None,
):
    """Grade a problem solution and return the grade results."""
    transcript = "dummy transcript"
    grade = asyncio.run(grade_problem(problem_id, transcript))
    with open(output_path, "w") as f:
        f.write(grade.metadata["AgentPatchGrader"]["junit"])
    print(grade)



async def validate_problem(problem_id: str) -> tuple[bool, dict[str, any]]:
    """Validate the test and golden patches for a problem."""

    # Get the problem specification
    spec = _get_spec(problem_id)

    # Check if required branch/commit info is available
    if not spec.base:
        raise ValueError(f"Problem {problem_id} missing base branch/commit")
    if not spec.test:
        raise ValueError(f"Problem {problem_id} missing test branch/commit")
    if not spec.golden:
        raise ValueError(f"Problem {problem_id} missing golden branch/commit")

    logger.info("=== VALIDATE_PROBLEM DEBUG ===")
    logger.info(f"Problem ID: {problem_id}")
    logger.info(f"Base: {spec.base}")
    logger.info(f"Test: {spec.test}")
    logger.info(f"Golden: {spec.golden}")
    logger.info(f"Test files: {spec.test_files}")

    # Create grading runner with the problem's branch/commit info
    runner = GradingRunner(
        base=spec.base,
        test=spec.test,
        golden=spec.golden,
        test_files=spec.test_files,
    )

    success, result = runner.validate_patches()

    if success:
        logger.info("Validation successful!")
    else:
        logger.error("Validation failed!")

    # Print the JUnit XML result if available
    if "junit" in result:
        print("\nJUnit XML Result:")
        print(result["junit"])

    return success, result



@click.command()
@click.argument("problem_id", envvar="PROBLEM_ID")
@click.option("--output_path", default="/tmp/validate_junit.xml", help="Path to output the JUNIT XML file")
def validate_problem_script(
    problem_id: str,
    output_path: str = None,
):
    """Validate a problem solution and return the validation results."""
    asyncio.run(validate_problem(problem_id))

@click.command()
def main():
    # Initialize and run the server as root; you can use files and services that require root permissions
    # once init is done, the server will run as the model user to prevent it from accessing problem data
    mcp.run(transport="stdio")
