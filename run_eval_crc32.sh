#!/bin/bash

# Set your API keys as environment variables before running:
# export HUD_API_KEY="your-hud-api-key"
# export ANTHROPIC_API_KEY="your-anthropic-api-key"

if [ -z "$HUD_API_KEY" ] || [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "Error: Please set HUD_API_KEY and ANTHROPIC_API_KEY environment variables"
    exit 1
fi

CRC32_HUD_DIR="/home/charlie/Desktop/GitHub/crc32/hud"
CONFIG_FILE="$CRC32_HUD_DIR/local-hud-crc32.json"

echo "==================================="
echo "🧪 CRC-32 Slicing Algorithm Eval"
echo "==================================="
echo ""
echo "📋 Problem Description"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Implement slicing_crc.sv:"
echo "    - High-performance CRC-32 calculator"
echo "    - Slicing-by-N algorithm"
echo "    - Configurable SLICE_LENGTH, INVERT_OUTPUT, REGISTER_OUTPUT"
echo ""
echo "📊 Test Suite: 10 tests"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  1. test_reset_initial_crc"
echo "  2. test_single_byte"
echo "  3. test_multiple_bytes_single_cycle"
echo "  4. test_full_slice"
echo "  5. test_multi_cycle_stream"
echo "  6. test_ethernet_frame"
echo "  7. test_partial_slices"
echo "  8. test_consecutive_packets"
echo "  9. test_random_vectors (20 random tests)"
echo "  10. test_long_packet (256 bytes)"
echo ""
echo "🎯 Running 5 episodes..."
echo ""

cd "$CRC32_HUD_DIR" || exit
uv run hud eval "$CONFIG_FILE" claude \
  --model claude-sonnet-4-5-20250929 \
  --max-steps 150 \
  --group-size 5 \
  --max-concurrent 2 \
  --yes \
  --verbose 2>&1 | tee eval_crc32_$(date +%Y%m%d_%H%M%S).log

echo ""
echo "✅ Done!"

