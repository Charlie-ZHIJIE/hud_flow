# Skid Buffer - HUD Environment

HUD evaluation environment for the Skid Buffer problem (AXI-Stream pipeline handshaking).

## Results

| Metric | Value |
|--------|-------|
| **Success Rate** | ~80% |
| **Mean Reward** | ~0.85 |
| **First Attempt** | ~20% (1-2/6) |
| **Tests** | 6 |

## Quick Start

```bash
docker build -t hud-skid-buffer:latest .

export HUD_API_KEY="your-key"
export ANTHROPIC_API_KEY="your-key"

./run_eval_skid_buffer.sh
```

## Key Challenge

FSM design with ready/valid handshaking and bypass mode.
