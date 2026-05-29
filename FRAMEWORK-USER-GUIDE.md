# Inductive Think-Aloud Framework Coding Tool — User Guide

> **Demo note:** This repository ships with synthetic transcripts under `demo_data/`. Run `./run_demo.sh` to start immediately. To work with your own data, copy `config/config_demo.yaml` to `config/config.yaml`, update the paths, and use `./run_research.sh` (see README).

## Quick Start

### 1. Start the Framework UI

```bash
./run_demo.sh
```

Or manually:

```bash
python src/inductive_ta/ui/app_framework.py --config config/config_demo.yaml
```

Open your browser to: `http://localhost:5002`

### 2. First Load: Project Validation

The UI will automatically validate your project files:

- `codebook/codebook.yaml` — Three-tier codebook definition
- `demo_data/ground_truth/SceneKeys.yaml` — Scene ground truth (scenes 1-5)
- `config/config_demo.yaml` — Project configuration

**If validation fails:**
- A red error screen will show specific issues to fix
- Fix the relevant YAML files and refresh the page

**If validation passes:**
- The participant list will appear with scene buttons

### 3. Select a Participant and Scene

Click any participant card, then click a scene button (1-5) to start coding.

---

## Interface Overview

The coder workspace uses a **tri-pane layout**:

### Left Panel: Navigator
- **Current participant and scene** (highlighted)
- **Scene list** (1-5) — click to switch scenes
- **Participant list** — click to switch participants
- **"Show Codebook" button** — opens codebook reference modal

### Center Panel: Transcript View
- **Performance strip** — Shows Correct/Incorrect, time, number of guesses
- **Ground truth strip** — Displays the scene's ground truth (e.g., "small blue cone")
- **Turn list** — One line per turn, with:
  - Line number
  - Tag (`[READING]`, `[THINKING]`, `[TYPING]`)
  - Raw text
  - Applied codes (Tier A/B, step-tags)
- **Episode bands** — Visual overlays showing episode spans
- **Action buttons** — Save All, Next Uncoded (N), Export Matrices, Download Snapshot, Undo, Redo
- **Range selection** — Click-and-drag to highlight a turn span; combine with *Use Selection* in the episode panel to seed hypotheses quickly

### Right Panel: Coding Sidebar
- **Mode toggle** — Switch between "Turn Coding", "Episode Mode", and "Scene Summary"
- **Turn Coding mode:**
  - Tier A operations (8 buttons with keyboard shortcuts 1-8)
  - Step tags (6 buttons with shortcuts H/T/R/M/.)
  - Tier B content (6 collapsible categories with checkboxes)
  - **Suggestions card** — Heuristic Tier A/B/Polarity/Confidence chips; click to accept or ignore
- **Episode Mode:**
  - Episode editor with all required fields
  - Tier C strategy codes (episode-level only)
  - Distance-to-truth calculator (with auto-explanations)
  - *Use Selection* button to pull the currently highlighted turns into the span fields
- **Scene Summary:** aggregated counts (operations, step-tags, HYP feature families, evidence policies, outcomes, distance-to-truth) plus a step-transition table updated live from your JSONL exports

---

## Turn-Based Coding Workflow

### Step 1: Select a Turn

**Method 1:** Click a turn in the transcript  
**Method 2:** Use arrow keys (`↑` / `↓`) to navigate

The selected turn will:
- Highlight with a blue background
- Show "Turn #X selected" in the sidebar
- Load its current codes into the sidebar
- **Shortcut:** Press `N` to jump to the next turn missing Tier A or key Tier B codes (also available via the *Next Uncoded* toolbar button)

### Step 2: Apply Tier A Operation (Required)

**Method 1:** Click an operation button in the sidebar

**Method 2:** Press number keys `1-8`:
- `1` — ORIENT
- `2` — OBSERVE_DESCRIBE
- `3` — INFERENCE
- `4` — HYPOTHESIZE
- `5` — TEST_SEEK_EVIDENCE
- `6` — EVALUATE_REVISE
- `7` — META_COGNITION
- `8` — RESPONSE_ENTRY

**Constraint:** Each turn must have exactly ONE Tier A operation.

### Step 3: Apply Step Tag (Optional)

**Method 1:** Click a step-tag button in the sidebar

**Method 2:** Press keyboard shortcuts:
- `H` — STEP_HYP (Hypothesis proposal)
- `T` — STEP_TEST_CONFIRM (Test with confirming evidence)
- `Shift+T` — STEP_TEST_DISCONFIRM (Test with disconfirming evidence)
- `R` — STEP_REVISE (Revision after conflict)
- `M` — STEP_OBS (Observation)
- `.` — STEP_COMMIT (Commit/answer)

**To clear:** Click "Clear Step" button

### Step 4: Apply Tier B Content (Multi-select)

Expand any of the 6 Tier B categories and check relevant boxes:

- **B1_FeatureFamily** — COLOR_Blue, SIZE_Small, ORIENTATION_Slanted, etc.
- **B2_Polarity** — Presence, Absence, Conditional
- **B3_EvidenceType** — PositiveCases, NegativeCases, Mixed
- **B4_Abstraction** — Token, Type, Schema
- **B5_Confidence** — Definite, Hedged, Disavowal
- **B6_ErrorType** — Perceptual, Logical_Overfit, Scope_Mismatch, Attribute_Confusion

**You can select multiple Tier B codes per turn.**

After selecting all relevant codes:
- Use **Apply to Selected Turn** to force a quick save (optional; autosave runs every 10 seconds)
- Review the **Suggestions** card for machine-flagged Tier A/B/Polarity/Confidence cues; click chips to auto-fill and then refine manually

### Step 5: Codes Auto-Apply

As you click operation buttons or check Tier B boxes, codes are **automatically applied** to the selected turn. Code chips appear in the turn's code row immediately.

### Step 6: Save (Manual or Auto)

**Manual save:**
- Press `Cmd+S` (Mac) or `Ctrl+S` (Windows/Linux)
- Click "Save All" button

**Autosave:**
- The UI autosaves every 10 seconds if there are unsaved changes

**Save status:** Bottom of center panel shows "Last saved: Xs ago"

---

## Episode Creation Workflow

Episodes represent a **contiguous run of turns** where the participant pursues one candidate hypothesis.

### Step 1: Switch to Episode Mode

**Method 1:** Click "Episode Mode" button in sidebar  
**Method 2:** Press `E` key

The sidebar switches to the episode editor.

### Step 2: Define Turn Span

Set the **start** and **end** turn indices for the episode.

Example:
- Start: `10`
- End: `25`

This means the episode covers turns 10 through 25.

**Tip:** Highlight a range of turns in the transcript (click-and-drag) and press **Use Selection** in the episode editor to populate the span instantly.

### Step 3: Fill Required Fields

**HypothesisVerbatim (Required):**
- Copy-paste or type the exact hypothesis the participant stated
- Example: "I think it's the small blue cone"

**FeatureBundle:**
- Click "+ Add Feature" to add tokens in `family=value` format
- Examples: `color=blue`, `size=small`, `orientation=slanted`
- These tokens will be compared to ground truth for distance calculation

**EvidenceCited:**
- Select from dropdown: PositiveCases, NegativeCases, or Mixed

**Confidence:**
- Select from dropdown: Definite, Hedged, or Disavowal

**Outcome:**
- Select from dropdown: accepted, revised, rejected, or pending

### Step 4: Apply Tier C Strategy Codes (Episode-Level)

Check any relevant strategy codes:

- **Search Mode:** BreadthFirst, DepthFirst
- **Hypothesis Management:** SingleTrack, Parallel, Elimination
- **Evidence Policy:** ConfirmOnly, Contrastive, Falsification
- **Complexity:** Atomic, Conjunctive, Relational
- **Cross-Scene:** Transfer, Perseveration, AdaptiveShift

**You can select multiple Tier C codes per episode.**

### Step 5: Calculate Distance-to-Truth

Click **"Calculate Distance"** button.

The UI will:
1. Send the FeatureBundle to the server
2. Compare it to the scene's ground truth
3. Return a distance category:
   - **ExactMatch** — All required features present
   - **FamilyMatch_Partial** — At least one correct family, but missing key dimensions
   - **FamilyMismatch** — No overlap with required features
   - **RuleFormMismatch** — Relational vs atomic mismatch

An explanation appears below the dropdown.

**You can also manually override** the distance by selecting from the dropdown.

### Step 6: Save Episode

Click **"Save Episode"** button.

The episode will:
- Be saved to `demo_exports/episodes.jsonl`
- Appear as a colored band overlaying the transcript
- Be assigned an episode ID (e.g., `P01_S1_EP0`)

### Step 7: Edit or Delete Episode

**To edit:**
- Click an episode band in the transcript
- The episode loads into the editor
- Modify fields and click "Save Episode"

**To delete:**
- Load the episode into the editor
- Click "Delete Episode" button
- Confirm deletion

**To create a new episode:**
- Click "New Episode" button to clear the editor
- Fill fields and save

---

## Keyboard Shortcuts Cheat Sheet

### Global
| Key | Action |
|---|---|
| `Cmd/Ctrl+S` | Save all changes |
| `Cmd/Ctrl+Z` | Undo |
| `Cmd/Ctrl+Shift+Z` | Redo |
| `↑` | Navigate to previous turn |
| `↓` | Navigate to next turn |
| `E` | Toggle Episode Mode |

### Tier A Operations (Turn Coding Mode)
| Key | Operation |
|---|---|
| `1` | OBSERVE_DESCRIBE |
| `2` | COMPARE_CONTRAST |
| `3` | HYPOTHESIZE |
| `4` | TEST_SEEK_EVIDENCE |
| `5` | EVALUATE_REVISE |
| `6` | META_COGNITION |
| `7` | RESPONSE_ENTRY |

### Step Tags (Turn Coding Mode)
| Key | Step Tag |
|---|---|
| `H` | STEP_HYP (Hypothesis) |
| `T` | STEP_TEST_CONFIRM |
| `Shift+T` | STEP_TEST_DISCONFIRM |
| `R` | STEP_REVISE |
| `M` | STEP_OBS (Observation) |
| `.` | STEP_COMMIT |

---

## Codebook Reference

### Accessing Definitions During Coding

Click **"Show Codebook"** button in the left navigator panel.

A modal will open displaying:
- **Tier A — Operations** with full definitions
- **Tier B — Content Categories** (B1-B6) with all codes and descriptions
- **Tier C — Strategy Codes** with definitions
- **Step Tags** with descriptions

**To close:** Click the `×` button or click outside the modal.

### Understanding the Three-Tier Structure

**Tier A (Operations):** Mutually exclusive, turn-level
- Describes what cognitive operation is happening in this turn

**Tier B (Content):** Multi-label, turn-level
- Describes the content of what's being said (features, evidence, confidence, etc.)
- Can apply multiple B codes to one turn

**Tier C (Strategy):** Multi-label, episode-level only
- Describes strategic patterns across multiple turns
- Only applied to episodes, not individual turns

---

## Data Export and Persistence

### What Gets Saved

All coding work is saved to **JSONL files** in `demo_exports/`:

1. **`demo_exports/corpus_enriched.jsonl`**
   - One line per turn
   - Contains: participant_id, scene, turn_index, raw_text, A_operation, B_content, step_tag, etc.

2. **`demo_exports/episodes.jsonl`**
   - One line per episode
   - Contains: episode_id, participant_id, scene, turn_span, HypothesisVerbatim, FeatureBundle, EvidenceCited, Confidence, Outcome, StrategyCodes, DistanceToTruth, Notes

3. **`demo_exports/CHANGELOG.jsonl`**
   - Audit trail of all edits
   - Contains: timestamp, participant_id, scene, action_type, before, after, notes

### Reloading Your Work

When you return to the UI:
1. Open the same participant and scene
2. The UI loads existing codes from `corpus_enriched.jsonl` and `episodes.jsonl`
3. All your codes and episodes will appear as you left them

### Exporting to CSV Matrices

Click **Export Matrices** in the toolbar to generate:
- `feature_attention_by_scene.csv` — Scene × FeatureFamily counts (HYPOTHESIZE turns only)
- `evidence_policy_by_outcome.csv` — EvidencePolicy × Outcome counts

Click **Download Snapshot** to download a ZIP archive of all current JSONL exports.

---

## Validation and Constraints

### Real-Time Validation

The UI enforces framework constraints:

**Turn-level:**
- Exactly ONE Tier A operation per turn (radio behavior)
- Step tag is optional
- Tier B codes are multi-select (any combination)

**Episode-level:**
- Required fields: HypothesisVerbatim, EvidenceCited, Confidence, Outcome
- Turn span must be valid (start ≤ end)

### Codebook Adherence

All codes in the UI are **loaded directly from `codebook/codebook.yaml`**.

If you add a new operation or code to the YAML file and restart the app, it will automatically appear in the UI. You can only select codes that exist in the dropdowns and checkboxes.

---

## Undo/Redo

The UI maintains a **history stack** with up to 50 snapshots.

**Undo (`Cmd/Ctrl+Z`):**
- Reverts to the previous state
- Moves current state to redo stack

**Redo (`Cmd/Ctrl+Shift+Z`):**
- Restores the next state from redo stack

**What gets captured:**
- All turn codes (A_operation, B_content, step_tag)
- All episodes

**What does not get captured:**
- Episode editor UI state (unsaved episode edits)
- Sidebar UI selections (which boxes are checked before applying)

---

## Visual Cues

### Turn Highlighting

- **Selected turn:** Blue background with blue left border
- **Hovered turn:** Light gray background

### Code Chips

- **Tier A chip:** Purple gradient, white text
- **Step tag chip:** Green background, white text
- **Tier B chip:** Light gray background, black text, bordered

### Episode Bands

- **Appearance:** Translucent blue overlay with blue left border
- **Label:** Shows episode index and first 50 characters of hypothesis
- **Hover:** Darkens slightly
- **Click:** Loads episode into editor (switches to Episode Mode)

### Ground Truth Strip

- **Background:** Light yellow (amber)
- **Border:** Orange left border
- **Content:** Displays scene key, features, and rule type

---

## Troubleshooting

**"No turn selected" alert when pressing number keys**  
Click a turn in the transcript first, or use arrow keys to select one.

**Codes disappear after refresh**  
Make sure you saved (Cmd+S or autosave). Check `demo_exports/corpus_enriched.jsonl` to verify data was written.

**Episode band does not appear after saving**  
Refresh the page. Episode bands are calculated based on DOM positions and may need a full re-render.

**"Episode not found" error when deleting**  
The episode may have already been deleted. Click "New Episode" to clear the editor.

**Distance calculator returns "Family Mismatch" for a correct hypothesis**  
Check that your FeatureBundle tokens match the ground truth format exactly. Use `family=value` format (e.g., `color=blue`, not `blue` alone).

**Keyboard shortcuts do not work**  
Make sure focus is not in an input field or textarea. Click somewhere in the transcript or sidebar (outside input fields) to regain focus.

---

## Best Practices

**Code in scene order.** Code Scene 1 through Scene 5 for each participant in sequence. This helps track cross-scene transfer and perseveration patterns.

**Save after each episode.** After creating an episode, press `Cmd+S` to ensure it is persisted before navigating away.

**Use step tags consistently.** Step tags enable sequential analysis. Apply them to every hypothesis proposal (`STEP_HYP`), every test turn (`STEP_TEST_CONFIRM` or `STEP_TEST_DISCONFIRM`), and every revision point (`STEP_REVISE`).

**Be consistent with Tier B.** Use the same granularity across all turns. If you mark `COLOR_Blue` for one hypothesis, apply the same logic to all comparable turns.

**Review episode boundaries carefully.** A well-formed episode starts when a participant proposes a new rule and ends when they abandon, revise, or commit to it. Avoid spanning multiple unrelated hypotheses or cutting off mid-reasoning.

**Use Distance-to-Truth to QA your coding.** If the result is "FamilyMismatch" but you expected "ExactMatch", verify that all required features are in the FeatureBundle and that the format matches the ground truth exactly.
