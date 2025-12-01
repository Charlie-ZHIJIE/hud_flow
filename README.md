# HUD Flow - Verilog Debugging Benchmark

A benchmark suite for evaluating LLM agents' ability to implement and debug Verilog/SystemVerilog designs through **iterative test feedback**.

## Key Innovation: Debug-Driven Code Generation

Unlike traditional code generation benchmarks that only measure **one-shot generation**, our framework captures the **iterative debugging process**:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Our Evaluation Flow                              │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐              │
│   │  First       │    │   Debug      │    │   Final      │              │
│   │  Attempt     │───▶│   Loop       │───▶│   Result     │              │
│   │  (10-20%)    │    │   (N iter)   │    │   (90-100%)  │              │
│   └──────────────┘    └──────────────┘    └──────────────┘              │
│         │                    │                    │                      │
│         ▼                    ▼                    ▼                      │
│   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐              │
│   │ = One-shot   │    │ Test Hints   │    │ Debugging    │              │
│   │   Generation │    │ + Debug      │    │ Capability   │              │
│   │   Capability │    │   Report     │    │ Measured     │              │
│   └──────────────┘    └──────────────┘    └──────────────┘              │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### Why First Attempt Matters

| Metric | Meaning | Use Case |
|--------|---------|----------|
| **First Attempt** | One-shot code generation quality | Baseline LLM capability |
| **Final Result** | After iterative debugging | Full agent capability |
| **Δ (Delta)** | Improvement through debugging | Learning signal for RL |

## Evaluation Workflow

```
Agent Workflow:
  1. Read Specification (docs/Specification.md)
  2. View Baseline Code (sources/*.sv)
  3. Implement Solution
  4. Call grade_problem() → Run cocotb tests
  5. If failed: Read DEBUG_REPORT.md        ◄── Key Innovation
  6. Analyze failures, fix code
  7. Repeat 4-6 until all tests pass
```

### Debug Report System

Each failed test generates **targeted debugging hints**:

```markdown
# 🔍 Debug Report - Attempt #3

## Summary
- Tests Passed: 3/10
- Reward: 0.300

## Failed Test: test_single_byte
**Error**: CRC mismatch
**Expected**: 0xD202EF8D
**Actual**: 0x00000000

💡 HINT: Check your table lookup logic. The first 4 bytes 
XOR with prev_crc before lookup. Verify num_input_bytes 
calculation from i_valid signal.
```

## Problems

| Branch | Problem | Difficulty | Tests | First Attempt | Final |
|--------|---------|------------|-------|---------------|-------|
| `simple_adder` | N-bit Adder | Easy | - | - | - |
| `simple_counter` | N-bit Counter | Easy | - | - | - |
| `skid_buffer` | AXI-Stream Skid Buffer | Medium | 6 | ~20% | ~85% |
| `crc32` | CRC-32 Slicing Algorithm | Medium | 10 | 10-20% | **100%** |
| `mac_rx` | MAC RX with CRC Check | Advanced | 10 | 20% | **90.7%** |

## Quick Start

```bash
# Clone specific problem branch
git clone -b crc32 https://github.com/Charlie-ZHIJIE/hud_flow.git
cd hud_flow

# Build Docker environment
docker build -t hud-crc32:latest .

# Set API keys
export HUD_API_KEY="your-key"
export ANTHROPIC_API_KEY="your-key"

# Run evaluation
./run_eval_crc32.sh
```

## Results Analysis

### CRC-32 Problem (10 agents)
- **First Attempt**: 10% perfect, 80% at 1/10, 10% at 0/10
- **Final Result**: **100% success rate**
- **Iterations**: 2-27 attempts to reach 100%

### MAC RX Problem (15 agents)  
- **First Attempt**: All agents at 2/10 (20%)
- **Final Result**: 73.3% perfect, 86.7% ≥90%
- **Key Challenge**: Hierarchical design (submodule instantiation)

## For RL Training

This benchmark provides rich training data:

```python
# Per-episode data structure
{
    "first_reward": 0.1,      # One-shot generation quality
    "final_reward": 1.0,      # After debugging
    "delta": 0.9,             # Learning signal
    "num_attempts": 6,        # Efficiency metric
    "trajectory": [           # Full debugging trace
        {"attempt": 1, "reward": 0.1, "action": "implement"},
        {"attempt": 2, "reward": 0.3, "action": "fix_syntax"},
        ...
        {"attempt": 6, "reward": 1.0, "action": "fix_edge_case"}
    ]
}
```

## Repository Structure

Each branch contains a complete, standalone HUD environment:

```
branch/
├── Dockerfile              # Container build
├── README.md               # Problem-specific docs
├── BENCHMARK_REPORT.md     # Evaluation results
├── local-hud-*.json        # HUD configuration
├── run_eval_*.sh           # Evaluation script
├── local-repos/problems/   # Problem files
│   ├── docs/Specification.md
│   ├── sources/*.sv
│   └── tests/test_*_hidden.py
└── src/hud_controller/     # MCP server + grading
```

## Related Work

Our approach combines:
- **Test-Driven Self-Debugging (TDSD)**: Iterative improvement using test feedback
- **Simulation-Guided Iterative Refinement (SGIR)**: RTL improvement via simulation

## Links

- **Verilog Problems**: https://github.com/Charlie-ZHIJIE/verilog-problems
- **HUD Framework**: https://hud.ai

---

*Framework: HUD + Cocotb 2.0 | Model: Claude Sonnet 4.5*
