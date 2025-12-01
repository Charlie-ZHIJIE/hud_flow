#!/usr/bin/env python3
"""
Cocotb testbench for rx_mac_stream module.

Tests the RX MAC stream with CRC verification using the slicing_crc submodule.
"""

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, FallingEdge, ClockCycles, Timer
from cocotb_test.simulator import run
import zlib
import random
import os
import shutil
from pathlib import Path
import pytest


def compute_crc32(data: bytes) -> int:
    """Compute CRC-32 using zlib (Ethernet polynomial)."""
    return zlib.crc32(data) & 0xFFFFFFFF


class RxMacTB:
    """Testbench helper class for rx_mac_stream."""
    
    def __init__(self, dut):
        self.dut = dut
        self.data_width = 32
        self.data_nbytes = self.data_width // 8
        
    async def reset(self):
        """Reset the DUT."""
        self.dut.i_reset.value = 1
        self.dut.s_axis_tdata.value = 0
        self.dut.s_axis_tkeep.value = 0
        self.dut.s_axis_tvalid.value = 0
        self.dut.s_axis_tlast.value = 0
        self.dut.i_rx_fcs.value = 0
        self.dut.i_rx_fcs_valid.value = 0
        await ClockCycles(self.dut.i_clk, 5)
        self.dut.i_reset.value = 0
        await ClockCycles(self.dut.i_clk, 2)
        
    async def send_frame(self, payload: bytes, fcs: int = None, fcs_valid: bool = True):
        """
        Send a frame through the input interface and return CRC check result.
        """
        if fcs is None:
            fcs = compute_crc32(payload)
            
        # Pad payload to multiple of data_nbytes
        num_beats = (len(payload) + self.data_nbytes - 1) // self.data_nbytes
        padded_payload = payload.ljust(num_beats * self.data_nbytes, b'\x00')
        
        crc_result = None
        
        # Send all beats
        for beat_idx in range(num_beats):
            is_last = (beat_idx == num_beats - 1)
            
            # Calculate data and keep for this beat
            start = beat_idx * self.data_nbytes
            end = start + self.data_nbytes
            beat_data = padded_payload[start:end]
            
            # Calculate keep mask
            remaining_bytes = len(payload) - start
            if remaining_bytes >= self.data_nbytes:
                keep = (1 << self.data_nbytes) - 1
            else:
                keep = (1 << remaining_bytes) - 1
                
            data_int = int.from_bytes(beat_data, 'little')
            
            # Drive inputs on falling edge (setup time before rising edge)
            await FallingEdge(self.dut.i_clk)
            self.dut.s_axis_tdata.value = data_int
            self.dut.s_axis_tkeep.value = keep
            self.dut.s_axis_tvalid.value = 1
            self.dut.s_axis_tlast.value = 1 if is_last else 0
            
            if is_last:
                self.dut.i_rx_fcs.value = fcs
                self.dut.i_rx_fcs_valid.value = 1 if fcs_valid else 0
            else:
                self.dut.i_rx_fcs.value = 0
                self.dut.i_rx_fcs_valid.value = 0
            
            # Wait for rising edge and sample outputs
            await RisingEdge(self.dut.i_clk)
            
            # Check for CRC result on tlast (sample before prev_crc updates propagate)
            if int(self.dut.m_axis_tlast.value) == 1 and int(self.dut.m_axis_tvalid.value) == 1:
                crc_result = int(self.dut.m_axis_tuser.value)
                    
        # Deassert valid
        self.dut.s_axis_tvalid.value = 0
        self.dut.s_axis_tlast.value = 0
        self.dut.i_rx_fcs_valid.value = 0
        await RisingEdge(self.dut.i_clk)
        
        return crc_result


# ============================================================================
# Test Cases
# ============================================================================

@cocotb.test()
async def test_reset_behavior(dut):
    """Test that reset properly initializes the module."""
    clock = Clock(dut.i_clk, 10, units="ns")
    cocotb.start_soon(clock.start())
    
    tb = RxMacTB(dut)
    await tb.reset()
    
    assert int(dut.m_axis_tvalid.value) == 0, "tvalid should be 0 after reset"
    

@cocotb.test()
async def test_single_frame_crc_ok(dut):
    """Test single frame with valid CRC."""
    clock = Clock(dut.i_clk, 10, units="ns")
    cocotb.start_soon(clock.start())
    
    tb = RxMacTB(dut)
    await tb.reset()
    
    payload = bytes([0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08])
    correct_fcs = compute_crc32(payload)
    
    crc_result = await tb.send_frame(payload, fcs=correct_fcs, fcs_valid=True)
    
    assert crc_result == 1, f"CRC should be OK (tuser=1), got {crc_result}"
    

@cocotb.test()
async def test_single_frame_crc_error(dut):
    """Test single frame with corrupted CRC."""
    clock = Clock(dut.i_clk, 10, units="ns")
    cocotb.start_soon(clock.start())
    
    tb = RxMacTB(dut)
    await tb.reset()
    
    payload = bytes([0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08])
    wrong_fcs = compute_crc32(payload) ^ 0xDEADBEEF
    
    crc_result = await tb.send_frame(payload, fcs=wrong_fcs, fcs_valid=True)
    
    assert crc_result == 0, f"CRC should be ERROR (tuser=0), got {crc_result}"


@cocotb.test()
async def test_fcs_not_valid(dut):
    """Test frame with i_rx_fcs_valid=0."""
    clock = Clock(dut.i_clk, 10, units="ns")
    cocotb.start_soon(clock.start())
    
    tb = RxMacTB(dut)
    await tb.reset()
    
    payload = bytes([0xAA, 0xBB, 0xCC, 0xDD])
    correct_fcs = compute_crc32(payload)
    
    crc_result = await tb.send_frame(payload, fcs=correct_fcs, fcs_valid=False)
    
    assert crc_result == 0, f"CRC should be ERROR when fcs_valid=0, got {crc_result}"


@cocotb.test()
async def test_multiple_frames(dut):
    """Test multiple consecutive frames."""
    clock = Clock(dut.i_clk, 10, units="ns")
    cocotb.start_soon(clock.start())
    
    tb = RxMacTB(dut)
    await tb.reset()
    
    # Frame 1: CRC OK
    payload1 = bytes([0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77, 0x88])
    crc1 = await tb.send_frame(payload1)
    assert crc1 == 1, f"Frame 1 CRC should be OK, got {crc1}"
    
    await ClockCycles(dut.i_clk, 3)
    
    # Frame 2: CRC error
    payload2 = bytes([0xAA, 0xBB, 0xCC, 0xDD])
    crc2 = await tb.send_frame(payload2, fcs=0x12345678, fcs_valid=True)
    assert crc2 == 0, f"Frame 2 CRC should be ERROR, got {crc2}"
    
    await ClockCycles(dut.i_clk, 3)
    
    # Frame 3: CRC OK
    payload3 = bytes([0x01, 0x02, 0x03, 0x04])
    crc3 = await tb.send_frame(payload3)
    assert crc3 == 1, f"Frame 3 CRC should be OK, got {crc3}"


@cocotb.test()
async def test_partial_last_beat(dut):
    """Test frame with partial bytes on last beat."""
    clock = Clock(dut.i_clk, 10, units="ns")
    cocotb.start_soon(clock.start())
    
    tb = RxMacTB(dut)
    await tb.reset()
    
    # 6 bytes = 1 full beat (4 bytes) + 1 partial beat (2 bytes)
    payload = bytes([0x01, 0x02, 0x03, 0x04, 0x05, 0x06])
    crc_result = await tb.send_frame(payload)
    
    assert crc_result == 1, f"CRC should be OK, got {crc_result}"


@cocotb.test()
async def test_minimum_frame(dut):
    """Test minimum size frame (4 bytes = 1 beat)."""
    clock = Clock(dut.i_clk, 10, units="ns")
    cocotb.start_soon(clock.start())
    
    tb = RxMacTB(dut)
    await tb.reset()
    
    payload = bytes([0x42, 0x43, 0x44, 0x45])
    crc_result = await tb.send_frame(payload)
    
    assert crc_result == 1, f"CRC should be OK for 4-byte frame, got {crc_result}"


@cocotb.test()
async def test_long_frame(dut):
    """Test longer frame (64 bytes)."""
    clock = Clock(dut.i_clk, 10, units="ns")
    cocotb.start_soon(clock.start())
    
    tb = RxMacTB(dut)
    await tb.reset()
    
    payload = bytes(range(64))
    crc_result = await tb.send_frame(payload)
    
    assert crc_result == 1, f"CRC should be OK for 64-byte frame, got {crc_result}"


@cocotb.test()
async def test_random_frames(dut):
    """Test with random payload data."""
    clock = Clock(dut.i_clk, 10, units="ns")
    cocotb.start_soon(clock.start())
    
    tb = RxMacTB(dut)
    await tb.reset()
    
    random.seed(42)
    
    for i in range(5):
        length = random.randint(4, 32)  # At least 4 bytes
        payload = bytes([random.randint(0, 255) for _ in range(length)])
        
        crc_result = await tb.send_frame(payload)
        assert crc_result == 1, f"Random frame {i} (len={length}) CRC should be OK, got {crc_result}"
        
        await ClockCycles(dut.i_clk, 2)


@cocotb.test()
async def test_back_to_back_frames(dut):
    """Test frames sent back-to-back with minimal gap."""
    clock = Clock(dut.i_clk, 10, units="ns")
    cocotb.start_soon(clock.start())
    
    tb = RxMacTB(dut)
    await tb.reset()
    
    for i in range(3):
        payload = bytes([i * 16 + j for j in range(8)])
        crc_result = await tb.send_frame(payload)
        assert crc_result == 1, f"Back-to-back frame {i} CRC should be OK, got {crc_result}"
        await ClockCycles(dut.i_clk, 1)


# ============================================================================
# Test Runner
# ============================================================================

def test_rx_mac_stream():
    """Run all cocotb tests for rx_mac_stream module."""
    proj_path = Path(__file__).resolve().parent.parent
    sources_path = proj_path / "sources"
    
    sim_build_dir = proj_path / "sim_build"
    sim_build_dir.mkdir(exist_ok=True)
    crc_tables_src = sources_path / "crc_tables.mem"
    crc_tables_dst = sim_build_dir / "crc_tables.mem"
    if crc_tables_src.exists():
        shutil.copy(crc_tables_src, crc_tables_dst)
    
    verilog_sources = [
        str(sources_path / "slicing_crc.sv"),
        str(sources_path / "rx_mac_stream.sv"),
    ]
    
    run(
        verilog_sources=verilog_sources,
        toplevel="rx_mac_stream",
        module="test_rx_mac_stream_hidden",
        sim_build=str(sim_build_dir),
        compile_args=["-g2012"],
    )


if __name__ == "__main__":
    test_rx_mac_stream()
