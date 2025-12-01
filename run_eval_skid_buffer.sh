#!/bin/bash

# Fine-grained Reward Evaluation - For RL training
# Reward: 0.0 to 1.0 based on passed_tests / total_tests

set -e

# API keys are expected to be set in the environment
# export ANTHROPIC_API_KEY="your-key"
# export HUD_API_KEY="your-key"

# Navigate to the evaluation directory
cd "/home/charlie/Desktop/GitHub/skid buffer/skid-buffer-eval"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🎯 Fine-grained Reward Evaluation (RL Training Data)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Reward Mode: FINE-GRAINED"
echo "  - 0/6 tests: 0.000"
echo "  - 1/6 tests: 0.167"
echo "  - 2/6 tests: 0.333"
echo "  - 3/6 tests: 0.500"
echo "  - 4/6 tests: 0.667"
echo "  - 5/6 tests: 0.833"
echo "  - 6/6 tests: 1.000"
echo ""
echo "Use case: RL fine-tuning with dense reward signal"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Run the HUD evaluation with fine-grained reward
uv run hud eval \
  "/home/charlie/Desktop/GitHub/skid buffer/skid-buffer-eval/local-hud-skid-buffer-FINEGRAINED.json" \
  claude \
  --model claude-sonnet-4-5-20250929 \
  --max-steps 150 \
  --group-size 10 \
  --yes \
  --verbose

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Fine-grained evaluation complete!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📊 Expected reward distribution:"
echo "  - More diverse rewards (0.0, 0.17, 0.33, 0.5, 0.67, 0.83, 1.0)"
echo "  - Better learning signal for RL training"
echo ""

