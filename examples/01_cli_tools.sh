#!/usr/bin/env bash
# ===========================================================================
# 01_cli_tools.sh — Y-GN CLI demonstration
#
# This script exercises the main ygn-core CLI subcommands.
# Prerequisites:
#   - ygn-core built and on PATH (see INSTALL.md, steps 3-5)
#
# Usage:
#   chmod +x examples/01_cli_tools.sh
#   ./examples/01_cli_tools.sh
# ===========================================================================

set -euo pipefail

echo "=== Y-GN Core CLI Demo ==="
echo ""

# --------------------------------------------------------------------------
# 1. Node status — prints the current node identity and runtime info.
# --------------------------------------------------------------------------
echo "--- ygn-core status ---"
ygn-core status
echo ""

# --------------------------------------------------------------------------
# 2. Config schema — exports the JSON schema that describes valid config.
# --------------------------------------------------------------------------
echo "--- ygn-core config schema ---"
ygn-core config schema
echo ""

# --------------------------------------------------------------------------
# 3. Tools list — shows all tools registered in the Core tool registry.
#    At minimum you should see the built-in "echo" tool.
# --------------------------------------------------------------------------
echo "--- ygn-core tools list ---"
ygn-core tools list
echo ""

# --------------------------------------------------------------------------
# 4. Registry self-info — displays this node's identity, role, and
#    trust tier as known to the node registry.
# --------------------------------------------------------------------------
echo "--- ygn-core registry self-info ---"
ygn-core registry self-info
echo ""

echo "=== Done ==="
