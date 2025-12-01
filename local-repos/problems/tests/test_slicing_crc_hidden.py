"""
Hidden test suite for slicing_crc module.

Tests CRC-32 calculation with various input patterns and configurations.
Reference: https://github.com/ttchisholm/slicing_crc/blob/main/tb/test_slicing_crc.py

This test suite includes a real-time timeout mechanism to handle implementations
that cause infinite loops or combinational cycles in the simulator.

NOTE: When simulation hangs (e.g., combinational loop), cocotb's simulation-time
timeout cannot trigger because simulation time doesn't advance. The TimeoutRunner
class handles this by killing the vvp process after a real-time timeout.
"""

import os
import shutil
from pathlib import Path

import pytest
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, FallingEdge, ClockCycles, Timer
from cocotb_tools.runner import get_runner
import zlib
import random

# Timeout in simulation time (microseconds)
# This helps catch tests that run too long in normal conditions
SIM_TIMEOUT_US = 1000  # 1ms simulation time


def ethernet_crc32(data: bytes) -> int:
    """Calculate Ethernet CRC-32 using zlib (same as reference implementation)."""
    return zlib.crc32(bytearray(data)) & 0xFFFFFFFF


class CRC_TB:
    """Testbench helper class (similar to reference implementation)."""
    
    def __init__(self, dut):
        self.dut = dut
        self.data_width = len(dut.i_data)
        self.slice_length = self.data_width // 8
        
        # Start clock (10ns period)
        cocotb.start_soon(Clock(dut.i_clk, 10, units="ns").start())
        
        # Initialize signals
        dut.i_data.value = 0
        dut.i_valid.value = 0
        dut.i_reset.value = 0
    
    async def reset(self):
        """Reset the DUT (using FallingEdge like reference)."""
        await FallingEdge(self.dut.i_clk)
        self.dut.i_reset.value = 1
        self.dut.i_valid.value = 0
        self.dut.i_data.value = 0
        await FallingEdge(self.dut.i_clk)
        self.dut.i_reset.value = 0
    
    async def send_data(self, data: bytes):
        """Send data to CRC calculator (using FallingEdge like reference)."""
        idx = 0
        while idx < len(data):
            await FallingEdge(self.dut.i_clk)
            
            # Determine how many bytes to send this cycle
            remaining = len(data) - idx
            num_bytes = min(remaining, self.slice_length)
            
            # Pack data (LSB first) - same as reference
            packed_data = 0
            valid_mask = 0
            for i in range(num_bytes):
                packed_data |= int(data[idx + i]) << (8 * i)
                valid_mask |= 1 << i
            
            self.dut.i_data.value = packed_data
            self.dut.i_valid.value = valid_mask
            
            idx += num_bytes
        
        # Clear valid after data sent
        await FallingEdge(self.dut.i_clk)
        self.dut.i_valid.value = 0
    
    async def get_crc(self) -> int:
        """Get CRC output, handling REGISTER_OUTPUT parameter."""
        # Check if output is registered
        try:
            register_output = int(self.dut.REGISTER_OUTPUT.value)
        except AttributeError:
            register_output = 1  # Default
        
        if register_output:
            await RisingEdge(self.dut.i_clk)
        
        return int(self.dut.o_crc.value)


@cocotb.test(timeout_time=SIM_TIMEOUT_US, timeout_unit="us")
async def test_reset_initial_crc(dut):
    """Test that reset sets CRC to initial value."""
    tb = CRC_TB(dut)
    await tb.reset()
    
    # With INVERT_OUTPUT=1 and INITIAL_CRC=0xFFFFFFFF, output should be 0x00000000
    await RisingEdge(dut.i_clk)
    expected = 0x00000000
    actual = int(dut.o_crc.value)
    
    assert actual == expected, f"Reset CRC: expected 0x{expected:08X}, got 0x{actual:08X}"


@cocotb.test(timeout_time=SIM_TIMEOUT_US, timeout_unit="us")
async def test_single_byte(dut):
    """Test CRC calculation with a single byte."""
    tb = CRC_TB(dut)
    await tb.reset()
    
    test_data = bytes([0x00])
    await tb.send_data(test_data)
    
    expected = ethernet_crc32(test_data)
    actual = await tb.get_crc()
    
    assert actual == expected, f"Single byte CRC: expected 0x{expected:08X}, got 0x{actual:08X}"


@cocotb.test(timeout_time=SIM_TIMEOUT_US, timeout_unit="us")
async def test_multiple_bytes_single_cycle(dut):
    """Test CRC calculation with multiple bytes in one cycle."""
    tb = CRC_TB(dut)
    await tb.reset()
    
    test_data = bytes([0x01, 0x02, 0x03, 0x04])
    await tb.send_data(test_data)
    
    expected = ethernet_crc32(test_data)
    actual = await tb.get_crc()
    
    assert actual == expected, f"Multi-byte CRC: expected 0x{expected:08X}, got 0x{actual:08X}"


@cocotb.test(timeout_time=SIM_TIMEOUT_US, timeout_unit="us")
async def test_full_slice(dut):
    """Test CRC calculation with full slice (8 bytes)."""
    tb = CRC_TB(dut)
    await tb.reset()
    
    test_data = bytes([0x00, 0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77])
    await tb.send_data(test_data)
    
    expected = ethernet_crc32(test_data)
    actual = await tb.get_crc()
    
    assert actual == expected, f"Full slice CRC: expected 0x{expected:08X}, got 0x{actual:08X}"


@cocotb.test(timeout_time=SIM_TIMEOUT_US, timeout_unit="us")
async def test_multi_cycle_stream(dut):
    """Test CRC calculation across multiple cycles (16 bytes)."""
    tb = CRC_TB(dut)
    await tb.reset()
    
    test_data = bytes(range(16))
    await tb.send_data(test_data)
    
    expected = ethernet_crc32(test_data)
    actual = await tb.get_crc()
    
    assert actual == expected, f"Multi-cycle CRC: expected 0x{expected:08X}, got 0x{actual:08X}"


@cocotb.test(timeout_time=SIM_TIMEOUT_US, timeout_unit="us")
async def test_ethernet_frame(dut):
    """Test CRC with realistic Ethernet frame data."""
    tb = CRC_TB(dut)
    await tb.reset()
    
    # Ethernet frame header (simplified)
    test_data = bytes([
        0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF,  # Dest MAC (broadcast)
        0x00, 0x11, 0x22, 0x33, 0x44, 0x55,  # Src MAC
        0x08, 0x00,                           # EtherType (IPv4)
        0x45, 0x00, 0x00, 0x1C,              # IP header start
    ])
    
    await tb.send_data(test_data)
    
    expected = ethernet_crc32(test_data)
    actual = await tb.get_crc()
    
    assert actual == expected, f"Ethernet frame CRC: expected 0x{expected:08X}, got 0x{actual:08X}"


@cocotb.test(timeout_time=SIM_TIMEOUT_US, timeout_unit="us")
async def test_partial_slices(dut):
    """Test CRC with varying partial slice sizes."""
    tb = CRC_TB(dut)
    
    for num_bytes in [1, 2, 3, 5, 7]:
        await tb.reset()
        
        test_data = bytes(range(num_bytes))
        await tb.send_data(test_data)
        
        expected = ethernet_crc32(test_data)
        actual = await tb.get_crc()
        
        assert actual == expected, \
            f"Partial slice ({num_bytes} bytes) CRC: expected 0x{expected:08X}, got 0x{actual:08X}"


@cocotb.test(timeout_time=SIM_TIMEOUT_US, timeout_unit="us")
async def test_consecutive_packets(dut):
    """Test CRC calculation for consecutive packets with reset between."""
    tb = CRC_TB(dut)
    
    # First packet
    await tb.reset()
    packet1 = bytes([0xAA, 0xBB, 0xCC, 0xDD])
    await tb.send_data(packet1)
    
    expected1 = ethernet_crc32(packet1)
    actual1 = await tb.get_crc()
    assert actual1 == expected1, f"Packet 1 CRC: expected 0x{expected1:08X}, got 0x{actual1:08X}"
    
    # Second packet (with reset)
    await tb.reset()
    packet2 = bytes([0x11, 0x22, 0x33, 0x44, 0x55])
    await tb.send_data(packet2)
    
    expected2 = ethernet_crc32(packet2)
    actual2 = await tb.get_crc()
    assert actual2 == expected2, f"Packet 2 CRC: expected 0x{expected2:08X}, got 0x{actual2:08X}"


@cocotb.test(timeout_time=5000, timeout_unit="us")
async def test_random_vectors(dut):
    """Test CRC with random data (similar to reference implementation)."""
    tb = CRC_TB(dut)
    
    # Use fixed seed for reproducibility
    random.seed(42)
    
    # Test 20 random vectors with varying lengths
    for i in range(20):
        await tb.reset()
        
        # Random length between 1 and 128 bytes
        length = random.randint(1, 128)
        test_data = bytes([random.randint(0, 255) for _ in range(length)])
        
        await tb.send_data(test_data)
        
        expected = ethernet_crc32(test_data)
        actual = await tb.get_crc()
        
        assert actual == expected, \
            f"Random test {i} ({length} bytes) CRC: expected 0x{expected:08X}, got 0x{actual:08X}"


@cocotb.test(timeout_time=5000, timeout_unit="us")
async def test_long_packet(dut):
    """Test CRC with longer packet (256 bytes)."""
    tb = CRC_TB(dut)
    await tb.reset()
    
    # 256 bytes of incrementing data
    test_data = bytes([i & 0xFF for i in range(256)])
    await tb.send_data(test_data)
    
    expected = ethernet_crc32(test_data)
    actual = await tb.get_crc()
    
    assert actual == expected, f"Long packet CRC: expected 0x{expected:08X}, got 0x{actual:08X}"


# -----------------------------------------------------------------------------
# Pytest entry point for running cocotb tests
# -----------------------------------------------------------------------------

import subprocess as sp
import sys
import threading
import time

# Maximum time (in seconds) for the entire simulation to run
# This prevents infinite loops from blocking the test suite
# Normal tests complete in < 1 second, so 5 seconds is plenty
SIMULATION_TIMEOUT_SEC = 5


@pytest.fixture(scope="module")
def sim_build():
    """Return the simulation build directory."""
    return Path(__file__).parent.parent / "sim_build"


class TimeoutRunner:
    """Wrapper to run cocotb tests with a real-time timeout."""
    
    def __init__(self, runner, timeout_sec):
        self.runner = runner
        self.timeout_sec = timeout_sec
        self.timed_out = False
        self.exception = None
    
    def run_with_timeout(self, **kwargs):
        """Run tests with timeout, killing vvp if it hangs."""
        def run_test():
            try:
                self.runner.test(**kwargs)
            except Exception as e:
                self.exception = e
        
        thread = threading.Thread(target=run_test)
        thread.start()
        thread.join(timeout=self.timeout_sec)
        
        if thread.is_alive():
            self.timed_out = True
            # Kill vvp process
            sp.run(["pkill", "-9", "-f", "vvp"], capture_output=True)
            sp.run(["pkill", "-9", "-f", "sim.vvp"], capture_output=True)
            # Wait a bit for cleanup
            time.sleep(0.5)
            thread.join(timeout=2)
        
        if self.exception:
            raise self.exception


def test_slicing_crc():
    """Run all cocotb tests for slicing_crc module."""
    sim = os.getenv("SIM", "icarus")
    
    proj_path = Path(__file__).resolve().parent.parent
    sources_path = proj_path / "sources"
    
    verilog_sources = [sources_path / "slicing_crc.sv"]
    
    runner = get_runner(sim)
    runner.build(
        verilog_sources=verilog_sources,
        hdl_toplevel="slicing_crc",
        always=True,
        build_args=["-g2012"] if sim == "icarus" else [],
    )
    
    # Copy crc_tables.mem to sim_build directory
    sim_build_dir = proj_path / "sim_build"
    sim_build_dir.mkdir(exist_ok=True)
    crc_tables_src = sources_path / "crc_tables.mem"
    crc_tables_dst = sim_build_dir / "crc_tables.mem"
    if crc_tables_src.exists():
        shutil.copy(crc_tables_src, crc_tables_dst)
    
    # Run the test with a timeout to catch infinite loops
    timeout_runner = TimeoutRunner(runner, SIMULATION_TIMEOUT_SEC)
    timeout_runner.run_with_timeout(
        hdl_toplevel="slicing_crc",
        test_module="test_slicing_crc_hidden",
        testcase="",  # Run all tests
    )
    
    if timeout_runner.timed_out:
        pytest.fail(
            f"Simulation timed out after {SIMULATION_TIMEOUT_SEC} seconds. "
            "Your implementation likely has an infinite loop or combinational cycle.\n\n"
            "Common causes:\n"
            "  1. Circular dependencies in always_comb blocks\n"
            "  2. Variables used before being assigned in combinational logic\n"
            "  3. Missing default assignments\n"
            "  4. Shared variables between multiple always_comb blocks\n\n"
            "Hint: Move all temporary variables INSIDE the always_comb block."
        )
