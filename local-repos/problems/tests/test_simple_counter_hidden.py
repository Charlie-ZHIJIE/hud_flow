import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer

@cocotb.test()
async def test_load_basic(dut):
    """Test basic load functionality - MUST FAIL if not implemented"""
    clock = Clock(dut.clk, 10, units="ns")
    cocotb.start_soon(clock.start())
    
    # Initialize all signals
    dut.rst.value = 0
    dut.ena.value = 0
    dut.load.value = 0
    dut.load_value.value = 0
    await RisingEdge(dut.clk)
    await Timer(1, units="ns")
    
    # Load a value - if not implemented, count will stay at 0 or X
    dut.load.value = 1
    dut.load_value.value = 42
    await RisingEdge(dut.clk)
    await Timer(1, units="ns")
    
    # This MUST fail if load is not implemented
    assert dut.count.value == 42, f"Load not implemented: expected 42, got {dut.count.value}"

@cocotb.test()
async def test_count_increment(dut):
    """Test counting - MUST FAIL if not implemented"""
    clock = Clock(dut.clk, 10, units="ns")
    cocotb.start_soon(clock.start())
    
    # Reset to 0
    dut.rst.value = 1
    dut.ena.value = 0
    dut.load.value = 0
    dut.load_value.value = 0
    await RisingEdge(dut.clk)
    await Timer(1, units="ns")
    
    # Release reset and enable counting
    dut.rst.value = 0
    dut.ena.value = 1
    await RisingEdge(dut.clk)
    await Timer(1, units="ns")
    
    # After one clock with ena=1, count should be 1
    # This MUST fail if ena logic is not implemented
    assert dut.count.value == 1, f"Count not working: expected 1, got {dut.count.value}"
    
    # Continue counting
    for i in range(2, 5):
        await RisingEdge(dut.clk)
        await Timer(1, units="ns")
        assert dut.count.value == i, f"Count error: expected {i}, got {dut.count.value}"

@cocotb.test()
async def test_reset(dut):
    """Test synchronous reset"""
    clock = Clock(dut.clk, 10, units="ns")
    cocotb.start_soon(clock.start())
    
    # Load a non-zero value first
    dut.rst.value = 0
    dut.ena.value = 0
    dut.load.value = 1
    dut.load_value.value = 99
    await RisingEdge(dut.clk)
    await Timer(1, units="ns")
    
    # Now test reset
    dut.load.value = 0
    dut.rst.value = 1
    await RisingEdge(dut.clk)
    await Timer(1, units="ns")
    assert dut.count.value == 0, f"Reset failed: expected 0, got {dut.count.value}"

@cocotb.test()
async def test_priority(dut):
    """Test priority: load > rst > ena"""
    clock = Clock(dut.clk, 10, units="ns")
    cocotb.start_soon(clock.start())
    
    # Reset first
    dut.rst.value = 1
    dut.ena.value = 0
    dut.load.value = 0
    dut.load_value.value = 0
    await RisingEdge(dut.clk)
    await Timer(1, units="ns")
    dut.rst.value = 0
    
    # Test: load has priority over ena
    dut.load.value = 1
    dut.load_value.value = 100
    dut.ena.value = 1
    await RisingEdge(dut.clk)
    await Timer(1, units="ns")
    assert dut.count.value == 100, f"Load priority failed: expected 100, got {dut.count.value}"
    
    # Test: load has priority over rst
    dut.load.value = 1
    dut.load_value.value = 200
    dut.rst.value = 1
    dut.ena.value = 1
    await RisingEdge(dut.clk)
    await Timer(1, units="ns")
    assert dut.count.value == 200, f"Load over rst failed: expected 200, got {dut.count.value}"
    
    # Test: rst has priority over ena
    dut.load.value = 0
    dut.rst.value = 1
    dut.ena.value = 1
    await RisingEdge(dut.clk)
    await Timer(1, units="ns")
    assert dut.count.value == 0, f"Rst over ena failed: expected 0, got {dut.count.value}"

def test_simple_counter_hidden_runner():
    """Pytest wrapper for cocotb tests"""
    import os
    from pathlib import Path
    from cocotb_tools.runner import get_runner

    sim = os.getenv("SIM", "icarus")
    proj_path = Path(__file__).resolve().parent.parent

    sources = [proj_path / "sources/simple_counter.sv"]
    runner = get_runner(sim)
    runner.build(
        sources=sources,
        hdl_toplevel="simple_counter",
        always=True,
    )
    runner.test(
        hdl_toplevel="simple_counter",
        test_module="test_simple_counter_hidden"
    )
