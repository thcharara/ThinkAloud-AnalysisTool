# Inductive Think-Aloud Coding Toolkit

A lightweight, codebook-driven interface for qualitative researchers who want to code think-aloud (or any protocol) transcripts directly from raw text. The UI lets you highlight spans, apply Tier A/B codes, and capture episodes/strategies without altering the original transcripts.

This repository now ships **demo data only**; all study data has been removed. Replace the demo folders with your own project to work on real material.

---

## Quick Demo (ships with synthetic sample data)

```bash
# Setup
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Run demo (uses synthetic P00, P01 transcripts)
./run_demo.sh

# Or manually:
python src/inductive_ta/ui/app_framework.py --config config/config_demo.yaml
```

Open <http://127.0.0.1:5002> and click a participant (P00/P01). You will see the **coding workspace**:

1. Click a turn in the transcript
2. Apply Tier A operation (keyboard shortcuts 1-8)
3. Add Tier B codes and step tags
4. Create episodes for hypothesis-testing sequences
5. All data saves to `demo_exports/` (safe to delete anytime)

**To reset demo exports:**
```bash
rm -r demo_exports/*
```

**To work on your own data:** Use `./run_research.sh` instead (see "Bring Your Own Data" below)

---

## Repository Layout

```
codebook/                   → Tier definitions (edit to match your study)
config/config_demo.yaml     → Demo configuration (tracked in Git)
config/config.yaml          → Your research config (not tracked—see .gitignore)
demo_data/                  → Synthetic transcripts/ground-truth for demos
demo_exports/               → Demo output directory (kept empty via gitkeep)
src/                        → Flask UI, analytics, exporters, CLI tools
scripts/                    → Utility scripts (cheatsheet builder, etc.)
tasks.py                    → CLI commands (ui, queries, purge-turns, etc.)
```

Files/directories containing study data are **excluded** via `.gitignore`:
- `clean_transcripts/`
- `exports/`
- `Inductive-ThinkAloud.nvpx`

When you bring your own corpus, keep it out of Git or use a private repo.

---

## Bring Your Own Data

**Two separate pathways keep demo and research data isolated:**

| Mode | Config File | Transcripts | Exports | Git Status |
|------|------------|-------------|---------|------------|
| **Demo** | `config/config_demo.yaml` | `demo_data/transcripts/` (P00, P01) | `demo_exports/` | Tracked in Git |
| **Research** | `config/config.yaml` | `clean_transcripts/` (your data) | `exports/` | In `.gitignore` |

### Quick Start for Your Own Data

1. **Create your local config:**
   ```bash
   cp config/config_demo.yaml config/config.yaml
   ```
   Edit `config/config.yaml` to point to your folders:
   ```yaml
   paths:
     transcripts_dir: clean_transcripts  # Your participant files
     exports_dir: exports                # Your coding work
     ground_truth: ground_truth/SceneKeys.yaml  # Optional
   ```

2. **Prepare transcripts** (UTF-8 text files):
   - One file per participant: `P01.txt`, `P02.txt`, etc.
   - Use scene headers: `Scene 1:`, `Scene 2:`, etc. (see `demo_data/transcripts/` for format)
   - Optional tags: `[READING]`, `[THINKING]`, `[TYPING]`

3. **Ground truth (optional):**
   - If you have correct answers, create a YAML file matching `demo_data/ground_truth/SceneKeys.yaml` format
   - If not, omit the `ground_truth` path—Distance-to-Truth is disabled, but all other features remain functional

4. **Run with your data:**
   ```bash
   ./run_research.sh
   # Or manually: python src/inductive_ta/ui/app_framework.py --config config/config.yaml
   ```

5. **Your data stays private:**
   - `config/config.yaml` is in `.gitignore` (never committed)
   - `clean_transcripts/` and `exports/` are in `.gitignore`
   - Only `config/config_demo.yaml` is tracked in Git (points to synthetic demo data)

### Switching Between Demo and Research

```bash
# Try the demo with synthetic data
./run_demo.sh

# Work on your real participants
./run_research.sh

# Or specify config manually
python src/inductive_ta/ui/app_framework.py --config config/config_demo.yaml
python src/inductive_ta/ui/app_framework.py --config config/config.yaml
```

---

## Features

- **Highlight-based coding:** select raw transcript text to create coded micro-units (turns) and meso-units (episodes).
- **Flexible codebook:** swap `codebook/codebook.yaml` for any Tier A/B/C schema (run `python -m src.inductive_ta.tools_codebook validate`).
- **Distance-to-Truth:** episodes are scored against optional ground truth at feature-family granularity (Exact / Partial / Mismatch); omit ground truth and every other feature still works.
- **Matrix & snapshot exports:** toolbar buttons generate feature-by-scene matrices (CSV) and download a zipped JSONL snapshot for archival.
- **Audit trail:** `CHANGELOG.jsonl` records every save (turns and episodes).
- **Demo friendly:** no proprietary data; includes synthetic transcripts + ground truth for trying the UI immediately.
- **Codespaces ready:** optional development container included (see below).

---

## GitHub Codespaces / Dev Containers

A devcontainer configuration is provided under `.devcontainer/`. Launching a Codespace gives you:
- Python 3.11, dependencies installed from `requirements.txt`
- Ready-to-run demo: `python src/inductive_ta/ui/app_framework.py`
- Inline coder accessible via forwarded port 5002

---

## Privacy & Ethics Checklist

- Do **not** commit real transcripts or exports.
- Keep `config/config.yaml` scoped to your private filesystem.
- Use `python tasks.py purge-turns` to remove any legacy auto-generated turn corpus.
- When sharing results, aggregate or anonymise span text carefully.

---

## Additional Documentation

- **[FRAMEWORK-USER-GUIDE.md](FRAMEWORK-USER-GUIDE.md)** — Comprehensive coding workflow guide
- **[KEYBOARD-SHORTCUTS.md](KEYBOARD-SHORTCUTS.md)** — Full reference for keyboard shortcuts
- **[memos/Codebook-CheatSheet.md](memos/Codebook-CheatSheet.md)** — Quick reference for all codes

---

## Contributing / Forking

1. Fork the repository.
2. Replace `demo_data` with your own synthetic or publicly shareable sample if you customize the demo.
3. Modify `codebook/codebook.yaml` to match your coding scheme.
4. Submit a PR or open an issue if you add features (e.g., episode-from-spans, span analytics).

MIT License © 2024—use responsibly and cite appropriately.

