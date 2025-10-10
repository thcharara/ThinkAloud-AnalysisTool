#!/usr/bin/env bash
set -euo pipefail
source .venv/bin/activate
python -m src.inductive_ta.tools_codebook validate
