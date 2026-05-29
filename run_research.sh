#!/bin/bash
# Run the Framework UI with YOUR RESEARCH data (local work)

echo "============================================================"
echo "🔬 Starting Research Mode (your participant data)"
echo "============================================================"
echo ""
echo "This mode uses:"
echo "  • Config: config/config.yaml (NOT tracked in Git)"
echo "  • Transcripts: clean_transcripts/"
echo "  • Exports: exports/"
echo ""
echo "Your data stays private and is never committed to Git."
echo "To try the demo instead, use: ./run_demo.sh"
echo "============================================================"
echo ""

if [ ! -f config/config.yaml ]; then
  echo "config/config.yaml not found."
  echo ""
  echo "Create it from the template, then point it at your data:"
  echo "  cp config/config_demo.yaml config/config.yaml"
  echo ""
  echo "Or run ./run_demo.sh to try the tool with synthetic data first."
  exit 1
fi

python src/inductive_ta/ui/app_framework.py --config config/config.yaml
