#!/usr/bin/env python3
"""
Grading runner script for agent patch testing.

This script:
1. Creates a copy of the git repo at baseline commit in /tmp
2. Applies test.patch to this repo (tests should fail)
3. Applies agent.patch to this repo (tests should pass)
4. Generates JUnit XML report at /tmp/grading_results.xml
"""

import logging
import os
import re
import subprocess
import sys
import threading
import uuid
from pathlib import Path

from .utils import merge_junits

logger = logging.getLogger(__name__)

class GradingRunner:
    """Handles the grading workflow for agent patch testing."""

    def __init__(
        self,
        base: str,
        test: str,
        golden: str,
        test_files: list[str],
        reward_mode: str = "fine_grained",  # "binary" or "fine_grained"
    ):
        """
        Initialize the grading runner.

        Args:
            base: The baseline branch name (preferred)
            test: The test branch name (optional, for logging)
            golden: The golden branch name (optional, for logging)
            test_files: List of test files to run
            reward_mode: "binary" (0/1) or "fine_grained" (0.0-1.0 based on passed/total)
        """
        # Determine what to use - branches take precedence
        self.use_base = base
        self.use_test = test
        self.use_golden = golden
        self.original_repo_path = "/home/ubuntu/example-verilog-codebase"
        self.test_patch_path = "/home/root/test.patch"
        self.golden_patch_path = "/home/root/golden.patch"
        self.grade_working_dir = "/tmp/grading_workspace_" + str(uuid.uuid4())
        self.test_files = test_files
        self.reward_mode = reward_mode  # "binary" or "fine_grained"

    def _format_junit_xml(self, test_name: str, failure_message: str | None = None, stdout: str = "", stderr: str = "") -> str:
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<testsuites>
  <testsuite name="{test_name}" tests="1" failures="1" errors="0" skipped="0">
    <testcase classname="{test_name}" name="test{test_name}" time="0.0">
      {f"<failure type='TestFailure'>\n{failure_message}\n</failure>" if failure_message else ""}
      <system-out>\n{stdout}\n</system-out>
      <system-err>\n{stderr}\n</system-err>
    </testcase>
  </testsuite>
</testsuites>"""

    def _parse_cocotb_results(self, output: str) -> tuple[int, int, list[str]]:
        """
        Parse cocotb test output to extract detailed results.
        
        Returns:
            (passed, total, failed_test_names)
        """
        # Try multiple patterns to find cocotb results
        
        # Pattern 1: TESTS=6 PASS=5 FAIL=1 SKIP=0 (standard cocotb format)
        match = re.search(r'TESTS=(\d+)\s+PASS=(\d+)\s+FAIL=(\d+)', output)
        if match:
            total = int(match.group(1))
            passed = int(match.group(2))
            failed = int(match.group(3))
            
            # Extract failed test names
            failed_tests = []
            for line in output.split('\n'):
                # Look for lines like: "** test_name  FAIL ..."
                if 'FAIL' in line and '**' in line:
                    # Extract test name
                    parts = line.split()
                    for i, part in enumerate(parts):
                        if 'test_' in part and part.startswith('test_'):
                            # Remove any trailing characters
                            test_name = part.split()[0] if ' ' in part else part
                            failed_tests.append(test_name)
                            break
            
            logger.info(f"Parsed cocotb results: {passed}/{total} passed, failed tests: {failed_tests}")
            return passed, total, failed_tests
        
        # Pattern 2: Look for "X passed" and "Y failed" in pytest output
        passed_match = re.search(r'(\d+)\s+passed', output)
        failed_match = re.search(r'(\d+)\s+failed', output)
        
        if passed_match or failed_match:
            passed = int(passed_match.group(1)) if passed_match else 0
            failed = int(failed_match.group(1)) if failed_match else 0
            total = passed + failed
            if total > 0:
                logger.info(f"Parsed pytest results: {passed}/{total} passed")
                return passed, total, []
        
        # Pattern 3: Look for "Failed X of Y tests" in cocotb output
        fail_match = re.search(r'Failed\s+(\d+)\s+of\s+(\d+)\s+tests', output)
        if fail_match:
            failed = int(fail_match.group(1))
            total = int(fail_match.group(2))
            passed = total - failed
            logger.info(f"Parsed cocotb summary: {passed}/{total} passed")
            return passed, total, []
        
        # Pattern 4: Look for individual test PASS/FAIL lines and count them
        pass_count = len(re.findall(r'\bPASS\b', output))
        fail_count = len(re.findall(r'\bFAIL\b', output))
        
        # Only use this if we found some results
        if pass_count > 0 or fail_count > 0:
            total = pass_count + fail_count
            # Sanity check: if total seems reasonable (1-20 tests)
            if 1 <= total <= 20:
                logger.info(f"Counted PASS/FAIL occurrences: {pass_count}/{total} passed")
                return pass_count, total, []
        
        # Fallback: assume 6 tests (our standard test count) and check for any failure
        logger.warning("Could not parse cocotb results, using 6-test fallback")
        if "FAIL" in output or "failed" in output.lower() or "error" in output.lower():
            # Try to estimate how many failed based on output patterns
            # Look for specific test failure indicators
            test_results = re.findall(r'test_\w+.*?(PASS|FAIL)', output, re.IGNORECASE)
            if test_results:
                passed = sum(1 for r in test_results if r.upper() == 'PASS')
                total = len(test_results)
                logger.info(f"Estimated from test patterns: {passed}/{total} passed")
                return passed, total, []
            
            # Default: 0 passed out of 6
            return 0, 6, ["unknown"]
        else:
            # All tests passed
            return 6, 6, []

    def run_tests(self) -> tuple[float, dict]:
        """
        Run tests and return reward based on reward_mode.
        
        Returns:
            (reward, metadata) where reward is in [0.0, 1.0]
        """
        logger.info(f"Running tests in {self.grade_working_dir} (reward_mode={self.reward_mode})")
        
        result = subprocess.run(
            ["sudo", "-u", "ubuntu", "bash", "-lc", " ".join(self._get_test_command())],
            cwd=Path(self.grade_working_dir),
            capture_output=True,
            text=True,
        )
        
        logger.info(f"Tests completed with code: {result.returncode}")
        logger.info(f"Test output: {result.stdout}")
        logger.info(f"Test error: {result.stderr}")
        
        # Parse test results
        passed, total, failed_tests = self._parse_cocotb_results(result.stdout + result.stderr)
        
        # Calculate reward based on mode
        if self.reward_mode == "binary":
            # Binary reward: 0.0 or 1.0
            reward = 1.0 if passed == total else 0.0
            logger.info(f"Test reward (binary): {reward:.1f} ({'PASS' if reward == 1.0 else 'FAIL'})")
        else:  # fine_grained
            # Fine-grained reward: passed/total
            reward = passed / total if total > 0 else 0.0
            logger.info(f"Test reward (fine-grained): {reward:.3f} ({passed}/{total} tests passed)")
        
        # Combine stdout and stderr for debug analysis
        full_output = f"=== STDOUT ===\n{result.stdout}\n\n=== STDERR ===\n{result.stderr}"
        
        # make a single junit xml file with the test results
        metadata = {
            "junit": self._format_junit_xml(
                "Tests", 
                f"Tests: {passed}/{total} passed" if passed < total else None,
                result.stdout, 
                result.stderr
            ),
            "passed": passed,
            "total": total,
            "reward": reward,
            "reward_mode": self.reward_mode,
            "failed_tests": failed_tests,
            "success": (passed == total),
            "test_output": full_output,  # Store for debugger
        }
        
        return reward, metadata


    def _get_build_command(self) -> list[str]:
        return ["true"] # no build needed for this project

    def _get_test_command(self) -> list[str]:
        return ["uv", "run", "pytest", *self.test_files]


    def run_grading(self) -> tuple[float, dict]:
        """Run the complete grading workflow. Returns (reward, metadata)."""
        logger.info("Starting grading workflow")
        # Step 1: Copy original repo to working dir
        logger.info(f"Copying original repo to {self.grade_working_dir}")
        subprocess.run(["sudo", "-u", "ubuntu", "cp", "-r", self.original_repo_path, self.grade_working_dir], check=True)
        logger.info(f"Copied original repo to {self.grade_working_dir}")

        # step 1.5 get the agent patch
        logger.info("Getting agent patch")
        patch = subprocess.run(["sudo", "-u", "ubuntu", "git", "diff"], capture_output=True, text=True).stdout

        # Step 2: apply test patch
        logger.info(f"Applying test patch to {self.grade_working_dir}")
        with open(self.test_patch_path) as f:
            subprocess.run(["sudo", "-u", "ubuntu", "git", "apply"], check=True, cwd=self.grade_working_dir, input=f.read().encode("utf-8"))
        logger.info(f"Applied test patch to {self.grade_working_dir}")

        # Step 3: compile the project (should work if the agent code compiles)
        logger.info(f"Compiling project in {self.grade_working_dir}")
        
        # Run build and stream output to stderr in real-time
        build_process = subprocess.Popen(
            ["sudo", "-u", "ubuntu", "bash", "-lc", " ".join(self._get_build_command())],
            cwd=self.grade_working_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        
        # Collect output for error reporting while streaming
        build_output = []
        
        def stream_build_stdout():
            """Stream stdout to stderr while collecting for error reporting."""
            for line in build_process.stdout:
                sys.stderr.write(line)
                sys.stderr.flush()
                build_output.append(line)
        
        def stream_build_stderr():
            """Stream stderr to stderr while collecting for error reporting."""
            for line in build_process.stderr:
                sys.stderr.write(line)
                sys.stderr.flush()
                build_output.append(line)
        
        # Start streaming threads
        stdout_thread = threading.Thread(target=stream_build_stdout)
        stderr_thread = threading.Thread(target=stream_build_stderr)
        
        stdout_thread.start()
        stderr_thread.start()
        
        # Wait for threads to complete
        stdout_thread.join()
        stderr_thread.join()
        
        # Wait for the process to complete
        build_result_code = build_process.wait()
        
        # Check exit code
        if build_result_code != 0:
            # Format compile error as JUnit XML
            xml_content = self._format_junit_xml("AgentPatchCompiles", "Agent patch compilation failed", "".join(build_output), "")
            logger.info(f"Compilation failed with exit code {build_result_code}")
            return 0.0, {
                "junit": xml_content, 
                "agent_patch": patch, 
                "passed": 0, 
                "total": 6, 
                "reward": 0.0, 
                "reward_mode": self.reward_mode,
                "compile_failed": True
            }
        
        logger.info(f"Compiled project successfully in {self.grade_working_dir}")

        # Step 4: Run tests and get reward (binary or fine-grained based on reward_mode)
        reward, data = self.run_tests()
        data["agent_patch"] = patch
        return reward, data

    def validate_patches(self) -> tuple[bool, dict]:
        """
        Copy the original repo to a temp directory.
        Apply test patch and ensure tests fail.
        Apply golden patch and ensure tests pass.
        """
        logger.info("Starting patch validation workflow")

        # Step 1: Copy original repo to working dir
        logger.info(f"Copying original repo to {self.grade_working_dir}")
        subprocess.run(
            ["sudo", "-u", "ubuntu", "cp", "-r", self.original_repo_path, self.grade_working_dir], check=True
        )
        logger.info(f"Copied original repo to {self.grade_working_dir}")

        # Step 2: Check that baseline compiles (without resetting)
        logger.info("Checking baseline compilation")
        try:
            logger.info(f"Compiling project at baseline in {self.grade_working_dir}")
            subprocess.run(
                ["sudo", "-u", "ubuntu", "bash", "-lc", " ".join(self._get_build_command())],
                cwd=self.grade_working_dir,
                timeout=1500,
                check=True,
                capture_output=True,
                text=True,
                env=dict(os.environ, HOME="/home/ubuntu"),
            )
            logger.info("Baseline compilation successful")
        except subprocess.CalledProcessError as e:
            # Format compile error as JUnit XML
            xml_content = self._format_junit_xml("BaselineCompiles", "Baseline compilation failed", e.stdout, e.stderr)
            logger.info("Baseline compilation failed, returning XML: {xml_content}")
            return False, {"junit": xml_content}

        # Step 3: Apply test patch
        logger.info(f"Applying test patch from {self.test_patch_path}")
        with open(self.test_patch_path) as f:
            patch = f.read().encode("utf-8")
        subprocess.run(
            ["sudo", "-u", "ubuntu", "git", "apply", "-"], input=patch, check=True, cwd=self.grade_working_dir
        )
        logger.info("Applied test patch successfully")

        # Step 4: Ensure that the tests fail
        logger.info("Running tests with test patch (expecting failure)")
        result = subprocess.run(
            ["sudo", "-u", "ubuntu", "bash", "-lc", " ".join(self._get_test_command())],
            cwd=self.grade_working_dir,
            capture_output=True,
            text=True,
            env=dict(os.environ, HOME="/home/ubuntu"),
        )

        if result.returncode == 0:
            # Tests passed when they should have failed (no failures in return code or XML)
            xml_content = self._format_junit_xml("TestPatchFailsTests", "Test patch did not cause tests to fail", result.stdout, result.stderr)
            logger.info(f"Tests passed with test patch (expected failure), returning XML: {xml_content}")
            return False, {"junit": xml_content}

        logger.info("Tests failed as expected with test patch")

        # Step 5: Reset the repo to the baseline
        logger.info(f"Resetting repo to baseline in {self.grade_working_dir}")
        subprocess.run(
            ["sudo", "-u", "ubuntu", "git", "reset", "--hard"], cwd=self.grade_working_dir, check=True
        )
        subprocess.run(
            ["sudo", "-u", "ubuntu", "git", "clean", "-fd"], cwd=self.grade_working_dir, check=True
        )
        logger.info("Reset repo to baseline successfully")

        # Step 6: Apply golden patch
        logger.info("Applying golden patch from {self.golden_patch_path}")
        with open(self.golden_patch_path) as f:
            patch = f.read().encode("utf-8")
        subprocess.run(
            ["sudo", "-u", "ubuntu", "git", "apply", "-"], input=patch, check=True, cwd=self.grade_working_dir
        )
        logger.info("Applied golden patch successfully")

        # Step 7: Apply test patch again
        logger.info(f"Applying test patch again in {self.grade_working_dir}")
        with open(self.test_patch_path) as f:
            patch = f.read().encode("utf-8")
        subprocess.run(
            ["sudo", "-u", "ubuntu", "git", "apply", "-"], input=patch, check=True, cwd=self.grade_working_dir
        )
        logger.info("Applied test patch again successfully")

        # Step 8: Compile with golden patch
        try:
            logger.info(f"Compiling project with golden patch in {self.grade_working_dir}")
            subprocess.run(
                ["sudo", "-u", "ubuntu", "bash", "-lc", " ".join(self._get_build_command())],
                cwd=self.grade_working_dir,
                timeout=1500,
                check=True,
                capture_output=True,
                text=True,
                env=dict(os.environ, HOME="/home/ubuntu"),
            )
            logger.info("Compilation with golden patch successful")
        except subprocess.CalledProcessError as e:
            # Format compile error as JUnit XML
            xml_content = self._format_junit_xml("GoldenPatchCompiles", "Golden patch compilation failed", e.stdout, e.stderr)
            logger.info(f"Golden patch compilation failed, returning XML: {xml_content}")
            return False, {"junit": xml_content}

        # Step 9: Ensure that the tests pass with golden patch
        logger.info("Running tests with golden patch (expecting success)")
        result = subprocess.run(
            ["sudo", "-u", "ubuntu", "bash", "-lc", " ".join(self._get_test_command())],
            cwd=self.grade_working_dir,
            capture_output=True,
            text=True,
            env=dict(os.environ, HOME="/home/ubuntu"),
        )

        if result.returncode != 0:
            # Tests failed when they should have passed
            xml_content = self._format_junit_xml(
                "GoldenPatchPassesTests", 
                f"Golden patch did not fix tests (returncode={result.returncode})", 
                result.stdout, 
                result.stderr
            )
            logger.info(f"Tests failed with golden patch (expected success), returning XML: {xml_content}")
            return False, {"junit": xml_content}

        logger.info("Tests passed as expected with golden patch")

        # All validation steps passed
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<testsuites>
  <testsuite name="PatchValidation" tests="6" failures="0" errors="0" skipped="0">
    <testcase classname="PatchValidation" name="testBaselineCompiles" time="0.0"/>
    <testcase classname="PatchValidation" name="testTestPatchApplies" time="0.0"/>
    <testcase classname="PatchValidation" name="testTestPatchFailsTests" time="0.0"/>
    <testcase classname="PatchValidation" name="testGoldenPatchApplies" time="0.0"/>
    <testcase classname="PatchValidation" name="testGoldenPatchCompiles" time="0.0"/>
    <testcase classname="PatchValidation" name="testGoldenPatchPassesTests" time="0.0"/>
  </testsuite>
</testsuites>"""

        logger.info("All validation steps passed")
        return True, {"junit": xml_content}
