# Keyboard Shortcuts — Quick Reference

## Global Shortcuts

| Shortcut | Action |
|---|---|
| **`Cmd+S`** / **`Ctrl+S`** | **Save all changes** |
| **`Cmd+Z`** / **`Ctrl+Z`** | **Undo** |
| **`Cmd+Shift+Z`** / **`Ctrl+Shift+Z`** | **Redo** |
| **`↑`** | Navigate to previous turn |
| **`↓`** | Navigate to next turn |
| **`E`** | Toggle Episode Mode |

---

## Tier A Operations (1-8)

Use these keys to apply Tier A operations to the selected turn:

| Key | Operation | Definition |
|---|---|---|
| **`1`** | **ORIENT** | Initial orientation and task framing |
| **`2`** | **OBSERVE_DESCRIBE** | Pure description of visible features; no inference |
| **`3`** | **INFERENCE** | Pattern-seeking, comparison, or preliminary reasoning |
| **`4`** | **HYPOTHESIZE** | Proposes a candidate rule (explicit or implicit) |
| **`5`** | **TEST_SEEK_EVIDENCE** | Checks candidate against panels; cites cases |
| **`6`** | **EVALUATE_REVISE** | Evaluates, revises, weakens, or abandons hypothesis |
| **`7`** | **META_COGNITION** | Comments on difficulty/strategy/uncertainty |
| **`8`** | **RESPONSE_ENTRY** | Typing/committing an answer |

---

## Step Tags

Use these keys to apply step-tags to the selected turn:

| Key | Step Tag | Meaning |
|---|---|---|
| **`H`** | **STEP_HYP** | Hypothesis proposal |
| **`T`** | **STEP_TEST_CONFIRM** | Test with confirming evidence |
| **`Shift+T`** | **STEP_TEST_DISCONFIRM** | Test with disconfirming evidence |
| **`R`** | **STEP_REVISE** | Revision after conflict |
| **`M`** | **STEP_OBS** | Observation |
| **`.`** (period) | **STEP_COMMIT** | Commit/answer |

---

## Workflow Tips

### Fast Turn Coding

1. **Select turn:** Click or use `↑`/`↓`
2. **Apply operation:** Press `1-8`
3. **Apply step tag (optional):** Press `H`, `T`, `R`, `M`, or `.`
4. **Check Tier B boxes:** Click checkboxes for features, confidence, etc.
5. **Move to next turn:** Press `↓`
6. **Repeat**

### Creating an Episode

1. **Switch to Episode Mode:** Press `E`
2. **Set turn span:** Enter start/end indices
3. **Fill hypothesis:** Type verbatim quote
4. **Add features:** Click "+ Add Feature" and type `color=blue`, `size=small`, etc.
5. **Select evidence/confidence/outcome:** Use dropdowns
6. **Calculate distance:** Click "Calculate Distance"
7. **Check strategy codes:** Select relevant Tier C codes
8. **Save:** Click "Save Episode"
9. **Return to turn coding:** Press `E` again

### Saving

- **Manual save:** Press `Cmd+S` / `Ctrl+S` after every few turns
- **Autosave:** Automatically saves every 30 seconds if there are changes
- **Visual confirmation:** Check "Last saved: Xs ago" at the bottom of the transcript panel

---

## Coding Rules

- **Tier A:** Exactly ONE operation per turn (mutually exclusive)
- **Step Tags:** Optional, but recommended for sequential analysis
- **Tier B:** Multiple codes allowed per turn
- **Tier C:** Episode-level only — not applied to individual turns

---

See [FRAMEWORK-USER-GUIDE.md](FRAMEWORK-USER-GUIDE.md) for detailed instructions.
