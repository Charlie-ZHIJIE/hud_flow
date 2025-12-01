# MAC RX Stream - HUD Environment

HUD evaluation environment for the MAC RX Stream problem (hierarchical design with CRC verification).

## Results

| Metric | Value |
|--------|-------|
| **Success Rate** | 73.3% perfect, 86.7% ≥90% |
| **Mean Reward** | 0.907 |
| **First Attempt** | 20% (2/10) |
| **Tests** | 10 |

## Quick Start

```bash
docker build -t hud-mac-rx:latest .

export HUD_API_KEY="your-key"
export ANTHROPIC_API_KEY="your-key"

./run_eval_mac_rx.sh
```

## Key Challenge

This is a **hierarchical design** problem - must instantiate `slicing_crc` submodule.
