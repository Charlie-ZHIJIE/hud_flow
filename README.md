# CRC-32 Slicing Algorithm - HUD Environment

HUD evaluation environment for the CRC-32 slicing-by-N algorithm problem.

## Results

| Metric | Value |
|--------|-------|
| **Success Rate** | 100% |
| **Mean Reward** | 1.000 |
| **First Attempt** | 10-20% |
| **Tests** | 10 |

## Quick Start

```bash
docker build -t verilog_crc32:latest .

export HUD_API_KEY="your-key"
export ANTHROPIC_API_KEY="your-key"

./run_eval_crc32.sh
```

## Files

- `Dockerfile` - Container build
- `local-hud-crc32.json` - HUD config
- `run_eval_crc32.sh` - Evaluation script
- `BENCHMARK_REPORT.md` - Detailed results
- `local-repos/problems/` - Problem files
