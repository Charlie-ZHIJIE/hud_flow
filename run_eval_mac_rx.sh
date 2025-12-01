#!/bin/bash

# API keys are expected to be set in the environment
# export HUD_API_KEY="..."
# export ANTHROPIC_API_KEY="..."

MAC_RX_HUD_DIR="/home/charlie/Desktop/GitHub/crc32/hud-mac_rx"
CONFIG_FILE="$MAC_RX_HUD_DIR/local-hud-mac_rx.json"

echo "==================================="
echo "🧪 MAC RX Stream Evaluation"
echo "==================================="
echo ""
echo "📋 Problem Description"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Implement rx_mac_stream.sv:"
echo "    - Ethernet MAC receive path component"
echo "    - Instantiate slicing_crc submodule"
echo "    - Verify CRC against received FCS"
echo "    - Report CRC status via m_axis_tuser"
echo ""
echo "📊 Test Suite: 10 tests"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  1. test_reset_behavior"
echo "  2. test_single_frame_crc_ok"
echo "  3. test_single_frame_crc_error"
echo "  4. test_fcs_not_valid"
echo "  5. test_multiple_frames"
echo "  6. test_partial_last_beat"
echo "  7. test_minimum_frame"
echo "  8. test_long_frame"
echo "  9. test_random_frames"
echo "  10. test_back_to_back_frames"
echo ""
echo "🎯 Running evaluation..."
echo ""

cd "$MAC_RX_HUD_DIR" || exit
uv run hud eval "$CONFIG_FILE" claude \
  --model claude-sonnet-4-5-20250929 \
  --max-steps 150 \
  --group-size 5 \
  --max-concurrent 2 \
  --yes \
  --verbose 2>&1 | tee eval_mac_rx_$(date +%Y%m%d_%H%M%S).log

echo ""
echo "✅ Done!"

