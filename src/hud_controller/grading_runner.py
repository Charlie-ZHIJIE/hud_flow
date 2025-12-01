#!/usr/bin/env python3
"""
Grading runner script for CRC-32 problem evaluation.

This script:
1. Creates a copy of the git repo at baseline commit in /tmp
2. Applies test.patch to this repo (tests should fail on baseline)
3. Runs tests against agent's implementation
4. Returns reward based on test results
"""

import logging
import os
import re
import subprocess
import sys
import threading
import uuid
from pathlib import Path

logger = logging.getLogger(__name__)


class GradingRunner:
    """Handles the grading workflow for CRC-32 evaluation."""

    def __init__(
        self,
        base: str,
        test: str,
        golden: str,
        test_files: list[str],
        reward_mode: str = "fine_grained",
    ):
        """
        Initialize the grading runner.

        Args:
            base: The baseline branch name
            test: The test branch name
            golden: The golden branch name
            test_files: List of test files to run
            reward_mode: "binary" (0/1) or "fine_grained" (0.0-1.0 based on passed/total)
        """
        self.use_base = base
        self.use_test = test
        self.use_golden = golden
        self.original_repo_path = "/home/ubuntu/example-verilog-codebase"
        self.test_patch_path = "/home/root/test.patch"
        self.golden_patch_path = "/home/root/golden.patch"
        self.grade_working_dir = "/tmp/grading_workspace_" + str(uuid.uuid4())[:8]
        self.test_files = test_files
        self.reward_mode = reward_mode

    def _format_junit_xml(self, test_name: str, failure_message: str | None = None, stdout: str = "", stderr: str = "") -> str:
        failure_xml = f"<failure type='TestFailure'>{failure_message}</failure>" if failure_message else ""
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<testsuites>
  <testsuite name="{test_name}" tests="1" failures="1" errors="0" skipped="0">
    <testcase classname="{test_name}" name="test{test_name}" time="0.0">
      {failure_xml}
      <system-out>{stdout}</system-out>
      <system-err>{stderr}</system-err>
    </testcase>
  </testsuite>
</testsuites>"""

    def _parse_cocotb_results(self, output: str, return_code: int = 0) -> tuple[int, int, list[str]]:
        """
        Parse cocotb test output to extract detailed results.
        
        Args:
            output: Combined stdout and stderr from test run
            return_code: Exit code from test process (0 = success, non-zero = failure)
        
        Returns:
            (passed, total, failed_test_names)
        """
        # Total number of tests in the CRC32 test suite
        TOTAL_TESTS = 10
        
        # Pattern 1: cocotb summary line - TESTS=N PASS=N FAIL=N SKIP=N
        # This is the most reliable indicator of actual test results
        match = re.search(r'TESTS=(\d+)\s+PASS=(\d+)\s+FAIL=(\d+)', output)
        if match:
            total = int(match.group(1))
            passed = int(match.group(2))
            
            failed_tests = []
            for line in output.split('\n'):
                if 'FAIL' in line and '**' in line:
                    # Extract test name from lines like "** test_xxx FAIL **"
                    test_match = re.search(r'\*\*\s*(test_\w+)\s+FAIL', line)
                    if test_match:
                        failed_tests.append(test_match.group(1))
            
            logger.info(f"Parsed cocotb results: {passed}/{total} passed")
            return passed, total, failed_tests
        
        # Pattern 2: Individual cocotb test results (PASS/FAIL lines)
        # Count lines like "** test_xxx PASS **" or "** test_xxx FAIL **"
        pass_matches = re.findall(r'\*\*\s*(test_\w+)\s+PASS\s*\*\*', output)
        fail_matches = re.findall(r'\*\*\s*(test_\w+)\s+FAIL\s*\*\*', output)
        
        pass_count = len(pass_matches)
        fail_count = len(fail_matches)
        
        if pass_count > 0 or fail_count > 0:
            total = pass_count + fail_count
            if 1 <= total <= 20:
                logger.info(f"Parsed cocotb results from PASS/FAIL lines: {pass_count}/{total} passed")
                return pass_count, total, fail_matches
        
        # Pattern 3: Check for compilation or syntax errors
        # These indicate the code couldn't even be compiled
        error_patterns = [
            r'syntax error',
            r'error:.*line \d+',
            r'Error compiling',
            r'vlog.*error',
            r'iverilog.*error',
            r'SyntaxError',
            r'ModuleNotFoundError',
            r'ImportError',
            r'AttributeError',
            r'NameError',
            r'TypeError',
        ]
        
        for pattern in error_patterns:
            if re.search(pattern, output, re.IGNORECASE):
                logger.warning(f"Detected compilation/syntax error (pattern: {pattern})")
                return 0, TOTAL_TESTS, ["compilation_error"]
        
        # Pattern 4: Check for assertion errors (test failures)
        if 'AssertionError' in output or 'assertion failed' in output.lower():
            logger.warning("Detected assertion error in test output")
            return 0, TOTAL_TESTS, ["assertion_error"]
        
        # Pattern 5: pytest reports failure but no cocotb output
        # This usually means the test couldn't even start (import error, etc.)
        if return_code != 0:
            # Check if pytest ran but cocotb didn't produce output
            if '1 failed' in output or 'FAILED' in output:
                logger.warning("pytest reported failure, but no cocotb results found")
                return 0, TOTAL_TESTS, ["test_setup_error"]
            
            # Generic failure
            logger.warning(f"Test process failed with return code {return_code}")
            return 0, TOTAL_TESTS, ["unknown_error"]
        
        # If return code is 0 and we got here, assume all tests passed
        # (cocotb output might have been truncated)
        logger.info("Return code 0, assuming all tests passed")
        return TOTAL_TESTS, TOTAL_TESTS, []

    def run_tests(self) -> tuple[float, dict]:
        """Run tests and return reward based on reward_mode."""
        logger.info(f"Running tests in {self.grade_working_dir}")
        
        # First, ensure uv sync is run to set up the environment
        sync_cmd = f"cd {self.grade_working_dir} && uv sync"
        sync_result = subprocess.run(
            ["sudo", "-u", "ubuntu", "bash", "-c", sync_cmd],
            capture_output=True,
            text=True,
            timeout=120,  # 2 minute timeout for sync
        )
        if sync_result.returncode != 0:
            logger.warning(f"uv sync failed: {sync_result.stderr}")
        
        # Build the test command with proper environment and timeout
        test_cmd = " ".join(self._get_test_command())
        # Use timeout command to ensure process is killed
        full_cmd = f"cd {self.grade_working_dir} && timeout 60 {test_cmd}"
        
        try:
            result = subprocess.run(
                ["sudo", "-u", "ubuntu", "bash", "-c", full_cmd],
                capture_output=True,
                text=True,
                timeout=90,  # 90 second timeout (should complete in ~1 second normally)
            )
        except subprocess.TimeoutExpired:
            logger.warning("Test execution timed out - likely infinite loop in implementation")
            # Kill any remaining vvp processes
            subprocess.run(["pkill", "-9", "-f", "vvp"], capture_output=True)
            return 0.0, {
                "passed": 0,
                "total": 10,
                "reward": 0.0,
                "reward_mode": self.reward_mode,
                "failed_tests": ["timeout"],
                "success": False,
                "test_output": "ERROR: Test execution timed out. Your implementation likely has an infinite loop or combinational cycle.",
            }
        
        logger.info(f"Tests completed with code: {result.returncode}")
        
        passed, total, failed_tests = self._parse_cocotb_results(
            result.stdout + result.stderr, 
            return_code=result.returncode
        )
        
        if self.reward_mode == "binary":
            reward = 1.0 if passed == total else 0.0
        else:
            reward = passed / total if total > 0 else 0.0
        
        full_output = f"=== STDOUT ===\n{result.stdout}\n\n=== STDERR ===\n{result.stderr}"
        
        metadata = {
            "junit": self._format_junit_xml(
                "CRC32Tests", 
                f"Tests: {passed}/{total} passed" if passed < total else None,
                result.stdout[:5000], 
                result.stderr[:5000]
            ),
            "passed": passed,
            "total": total,
            "reward": reward,
            "reward_mode": self.reward_mode,
            "failed_tests": failed_tests,
            "success": (passed == total),
            "test_output": full_output,
        }
        
        return reward, metadata

    def _get_build_command(self) -> list[str]:
        return ["true"]

    def _get_test_command(self) -> list[str]:
        # -s: don't capture stdout (needed to see cocotb test results)
        # -v: verbose output
        return ["uv", "run", "pytest", "-v", "-s", *self.test_files]

    def run_grading(self) -> tuple[float, dict]:
        """Run the complete grading workflow."""
        logger.info("Starting grading workflow")
        
        # Step 1: Copy original repo
        subprocess.run(["sudo", "-u", "ubuntu", "cp", "-r", self.original_repo_path, self.grade_working_dir], check=True)
        
        # Step 1.5: Get agent patch (diff from current working directory)
        patch_result = subprocess.run(
            ["sudo", "-u", "ubuntu", "git", "diff"], 
            capture_output=True, 
            text=True,
            cwd=self.original_repo_path
        )
        patch = patch_result.stdout
        
        # Step 2: Apply test patch (if exists and non-empty)
        if os.path.exists(self.test_patch_path):
            with open(self.test_patch_path) as f:
                test_patch_content = f.read()
            if test_patch_content.strip():
                try:
                    subprocess.run(
                        ["sudo", "-u", "ubuntu", "git", "apply"], 
                        check=True, 
                        cwd=self.grade_working_dir, 
                        input=test_patch_content.encode("utf-8")
                    )
                except subprocess.CalledProcessError as e:
                    logger.warning(f"Failed to apply test patch: {e}")
        
        # Step 3: Build (no-op for this project)
        build_process = subprocess.Popen(
            ["sudo", "-u", "ubuntu", "bash", "-c", " ".join(self._get_build_command())],
            cwd=self.grade_working_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        
        build_output = []
        
        def stream_output(pipe, output_list):
            for line in pipe:
                sys.stderr.write(line)
                sys.stderr.flush()
                output_list.append(line)
        
        stdout_thread = threading.Thread(target=stream_output, args=(build_process.stdout, build_output))
        stderr_thread = threading.Thread(target=stream_output, args=(build_process.stderr, build_output))
        
        stdout_thread.start()
        stderr_thread.start()
        stdout_thread.join()
        stderr_thread.join()
        
        build_result_code = build_process.wait()
        
        if build_result_code != 0:
            xml_content = self._format_junit_xml("AgentPatchCompiles", "Agent patch compilation failed", "".join(build_output), "")
            return 0.0, {
                "junit": xml_content, 
                "agent_patch": patch, 
                "passed": 0, 
                "total": 10, 
                "reward": 0.0, 
                "reward_mode": self.reward_mode,
                "compile_failed": True
            }
        
        # Step 4: Run tests
        reward, data = self.run_tests()
        data["agent_patch"] = patch
        return reward, data
