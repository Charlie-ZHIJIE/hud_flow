import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer

@cocotb.test()
async def test_addition(dut):
    """Test basic addition"""
    clock = Clock(dut.clk, 10, units="ns")
    cocotb.start_soon(clock.start())
    
    await RisingEdge(dut.clk)
    dut.a.value = 5
    dut.b.value = 3
    await RisingEdge(dut.clk)
    await Timer(1, units="ns")  # Wait for non-blocking assignment to complete
    assert dut.sum.value == 8, f"Expected 8, got {dut.sum.value}"

# ✅ CRITICAL: Pytest wrapper function
def test_simple_adder_hidden_runner():
    import os
    from pathlib import Path
    from cocotb_tools.runner import get_runner
    
    sim = os.getenv("SIM", "icarus")
    proj_path = Path(__file__).resolve().parent.parent
    
    sources = [proj_path / "sources/simple_adder.sv"]  # Note: sources/ not rtl/
    
    runner = get_runner(sim)
    runner.build(
        sources=sources,
        hdl_toplevel="simple_adder",
        always=True,
    )
    runner.test(
        hdl_toplevel="simple_adder",
        test_module="test_simple_adder_hidden"
    )

