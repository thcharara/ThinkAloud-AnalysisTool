#!/bin/bash
# Run the Framework UI with DEMO data (for GitHub users trying it out)

echo "============================================================"
echo "🎭 Starting Demo Mode (synthetic data only)"
echo "============================================================"
echo ""
echo "This mode uses:"
echo "  • Config: config/config_demo.yaml"
echo "  • Transcripts: demo_data/transcripts/ (P00, P01)"
echo "  • Exports: demo_exports/"
echo ""
echo "To work on your own research data, use: ./run_research.sh"
echo "============================================================"
echo ""

python src/inductive_ta/ui/app_framework.py --config config/config_demo.yaml
