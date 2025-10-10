/**
 * Inductive Think-Aloud Framework Coder V2
 * Text-highlighting based coding interface
 */

// ===== STATE MANAGEMENT =====
class CoderState {
    constructor(appData) {
        this.participantId = appData.participant_id;
        this.scene = appData.scene;
        this.sceneKey = appData.scene_key;
        this.rawTranscript = appData.raw_transcript;

        // Units of analysis - load existing data if available
        this.microUnits = appData.turns || []; // Turns
        this.mesoUnits = appData.episodes || []; // Episodes
        this.macroData = {}; // Participant-level

        // Current selection
        this.currentMode = 'micro';
        this.currentUnit = null;
        this.selectedText = null;
        this.selectedRange = null;
        this.selectedTurnRange = { start: null, end: null }; // For turn range selection

        // History for undo/redo
        this.history = [];
        this.historyIndex = -1;
        this.maxHistory = 50;

        // Autosave
        this.lastSaved = null;
        this.isDirty = false;
    }

    // Add to history
    snapshot() {
        const state = {
            microUnits: JSON.parse(JSON.stringify(this.microUnits)),
            mesoUnits: JSON.parse(JSON.stringify(this.mesoUnits)),
            timestamp: Date.now()
        };

        // Remove future history if we're not at the end
        if (this.historyIndex < this.history.length - 1) {
            this.history = this.history.slice(0, this.historyIndex + 1);
        }

        this.history.push(state);
        if (this.history.length > this.maxHistory) {
            this.history.shift();
        } else {
            this.historyIndex++;
        }

        this.isDirty = true;
    }

    undo() {
        if (this.historyIndex > 0) {
            this.historyIndex--;
            const state = this.history[this.historyIndex];
            this.microUnits = JSON.parse(JSON.stringify(state.microUnits));
            this.mesoUnits = JSON.parse(JSON.stringify(state.mesoUnits));
            return true;
        }
        return false;
    }

    redo() {
        if (this.historyIndex < this.history.length - 1) {
            this.historyIndex++;
            const state = this.history[this.historyIndex];
            this.microUnits = JSON.parse(JSON.stringify(state.microUnits));
            this.mesoUnits = JSON.parse(JSON.stringify(state.mesoUnits));
            return true;
        }
        return false;
    }
}

let state = null;

// ===== INITIALIZATION =====
document.addEventListener('DOMContentLoaded', () => {
    state = new CoderState(window.APP_DATA);

    // Take initial snapshot
    state.snapshot();

    setupTextSelection();
    setupUnitCreation();
    setupCodingPanels();
    setupModeToggle();
    setupKeyboardShortcuts();
    setupSaveButtons();
    setupCategoryToggles();
    setupHelpModal();
    setupEpisodeTypeToggle();
    setupAutoFillSpan();
    setupVoiceDictation();

    renderTranscript();
    updateUnitsSidebar();
    updateSaveStatus();
});

// ===== TEXT SELECTION =====
function setupTextSelection() {
    const transcriptLines = document.getElementById('transcript-lines');

    transcriptLines.addEventListener('mouseup', () => {
        const selection = window.getSelection();
        if (selection.toString().trim().length > 0) {
            state.selectedText = selection.toString().trim();
            state.selectedRange = selection.getRangeAt(0);
            updateSelectionInfo();
        }
    });
}

function updateSelectionInfo() {
    const selectionInfo = document.getElementById('selection-info');
    if (state.selectedText) {
        const wordCount = state.selectedText.split(/\s+/).length;
        selectionInfo.textContent = `Selected: ${wordCount} words`;
    } else {
        selectionInfo.textContent = '';
    }
}

// ===== UNIT CREATION =====
function setupUnitCreation() {
    document.getElementById('btn-create-micro').addEventListener('click', createMicroUnit);
    document.getElementById('btn-create-meso').addEventListener('click', createMesoUnit);
}

function createMicroUnit() {
    if (!state.selectedText) {
        alert('Please select text from the transcript first');
        return;
    }

    const turnIndex = state.microUnits.length;
    const microUnit = {
        turn_index: turnIndex,
        participant_id: state.participantId,
        scene: state.scene,
        raw_text: state.selectedText,
        tag: extractTag(state.selectedText),
        A_operation: null,
        B_content: [],
        step_tag: null,
        char_start: null,
        char_end: null
    };

    state.microUnits.push(microUnit);
    state.currentUnit = microUnit;
    state.currentMode = 'micro';

    state.snapshot();
    renderTranscript();
    updateUnitsSidebar();
    updateCurrentUnitInfo();
    highlightTranscriptUnit(turnIndex, 'micro');

    // Clear selection
    window.getSelection().removeAllRanges();
    state.selectedText = null;
    updateSelectionInfo();
}

function createMesoUnit() {
    if (!state.selectedText) {
        alert('Please select text from the transcript first');
        return;
    }

    const episodeIndex = state.mesoUnits.length;
    const mesoUnit = {
        episode_id: `${state.participantId}_S${state.scene}_EP${episodeIndex}`,
        episode_index: episodeIndex,
        participant_id: state.participantId,
        scene: state.scene,
        turn_span_start: null,
        turn_span_end: null,
        episode_type: 'hypothesis_episode',  // default
        chunk_type: null,
        chunk_description: '',
        HypothesisVerbatim: state.selectedText,
        FeatureBundle: [],
        EvidenceCited: null,
        Confidence: null,
        Outcome: null,
        StrategyCodes: [],
        DistanceToTruth: null,
        Notes: ''
    };

    state.mesoUnits.push(mesoUnit);
    state.currentUnit = mesoUnit;
    state.currentMode = 'meso';

    // Switch to meso mode
    switchMode('meso');

    state.snapshot();
    renderTranscript();
    updateUnitsSidebar();
    updateCurrentUnitInfo();
    populateEpisodeForm(mesoUnit);

    // Clear selection
    window.getSelection().removeAllRanges();
    state.selectedText = null;
    updateSelectionInfo();
}

function extractTag(text) {
    if (text.includes('[READING]')) return '[READING]';
    if (text.includes('[THINKING]')) return '[THINKING]';
    if (text.includes('[TYPING]')) return '[TYPING]';
    return null;
}

// ===== TRANSCRIPT RENDERING =====
function renderTranscript() {
    const transcriptLines = document.getElementById('transcript-lines');
    transcriptLines.innerHTML = '';

    if (!state.rawTranscript) {
        transcriptLines.textContent = 'No transcript available. Please check data source.';
        return;
    }

    let transcriptText = state.rawTranscript;
    let htmlContent = '';
    let lastIndex = 0;

    // Build array of all coded spans with their positions
    const codedSpans = state.microUnits.map((unit, idx) => {
        const startPos = transcriptText.indexOf(unit.raw_text, lastIndex);
        if (startPos === -1) return null;

        const endPos = startPos + unit.raw_text.length;
        return {
            start: startPos,
            end: endPos,
            unit: unit,
            index: idx,
            operation: unit.A_operation
        };
    }).filter(span => span !== null).sort((a, b) => a.start - b.start);

    // Render transcript with inline highlights
    lastIndex = 0;
    codedSpans.forEach(span => {
        // Add text before this span (unhighlighted)
        if (span.start > lastIndex) {
            htmlContent += escapeHtml(transcriptText.substring(lastIndex, span.start));
        }

        // Add highlighted span with color based on Tier A operation
        const colorClass = getTierAColorClass(span.operation);
        htmlContent += `<span class="highlighted-turn ${colorClass}" data-unit-index="${span.index}" data-unit-type="micro">${escapeHtml(span.unit.raw_text)}</span>`;

        lastIndex = span.end;
    });

    // Add remaining text after last span
    if (lastIndex < transcriptText.length) {
        htmlContent += escapeHtml(transcriptText.substring(lastIndex));
    }

    transcriptLines.innerHTML = htmlContent;

    // Add click handlers to highlighted turns
    document.querySelectorAll('.highlighted-turn').forEach(el => {
        el.addEventListener('click', (e) => {
            const unitIndex = parseInt(el.dataset.unitIndex);
            const unit = state.microUnits[unitIndex];

            // Check if we're in meso mode - if so, handle turn range selection
            if (state.currentMode === 'meso') {
                e.stopPropagation();
                e.preventDefault();

                // Handle shift-click for turn range selection
                if (e.shiftKey && state.selectedTurnRange.start !== null) {
                    state.selectedTurnRange.end = unitIndex;
                } else {
                    // Regular click - start new range selection
                    state.selectedTurnRange.start = unitIndex;
                    state.selectedTurnRange.end = unitIndex;
                }

                updateTurnRangeHighlight();

                // Auto-fill the turn span inputs immediately
                const start = Math.min(state.selectedTurnRange.start, state.selectedTurnRange.end);
                const end = Math.max(state.selectedTurnRange.start, state.selectedTurnRange.end);
                document.getElementById('meso-start').value = start;
                document.getElementById('meso-end').value = end;

                console.log(`Turn range selected: ${start} → ${end}`);
            } else {
                // In micro mode, select the unit for editing
                if (unit) {
                    selectUnit(unit, 'micro');
                }
            }
        });
    });

    // Render episode brackets
    renderEpisodeBrackets();
}

function updateTurnRangeHighlight() {
    // Visual feedback for selected turn range
    document.querySelectorAll('.highlighted-turn').forEach(el => {
        el.classList.remove('range-selected');
    });

    if (state.selectedTurnRange.start !== null && state.selectedTurnRange.end !== null) {
        const start = Math.min(state.selectedTurnRange.start, state.selectedTurnRange.end);
        const end = Math.max(state.selectedTurnRange.start, state.selectedTurnRange.end);

        for (let i = start; i <= end; i++) {
            const el = document.querySelector(`[data-unit-index="${i}"][data-unit-type="micro"]`);
            if (el) {
                el.classList.add('range-selected');
            }
        }
    }
}

function renderEpisodeBrackets() {
    const bracketsContainer = document.getElementById('episode-brackets');
    const transcriptLines = document.getElementById('transcript-lines');
    if (!bracketsContainer || !transcriptLines) return;

    bracketsContainer.innerHTML = '';

    state.mesoUnits.forEach((episode, episodeIdx) => {
        const startIdx = episode.turn_span_start;
        const endIdx = episode.turn_span_end;

        // Find DOM elements for start and end turns
        const startEl = document.querySelector(`[data-unit-index="${startIdx}"][data-unit-type="micro"]`);
        const endEl = document.querySelector(`[data-unit-index="${endIdx}"][data-unit-type="micro"]`);

        if (startEl && endEl) {
            // Calculate positions relative to transcript-lines parent
            const transcriptRect = transcriptLines.getBoundingClientRect();
            const startRect = startEl.getBoundingClientRect();
            const endRect = endEl.getBoundingClientRect();

            // Use offsetTop for scroll-independent positioning
            const startOffset = startEl.offsetTop;
            const endOffset = endEl.offsetTop + endEl.offsetHeight;
            const height = endOffset - startOffset;

            const bracket = document.createElement('div');
            bracket.className = 'episode-bracket';
            bracket.style.top = `${startOffset}px`;
            bracket.style.height = `${height}px`;
            bracket.dataset.episodeIndex = episodeIdx;

            const isChunk = episode.episode_type === 'reasoning_chunk';
            if (isChunk) {
                bracket.classList.add('chunk-type');
            }

            // Highlight if this is the current episode
            if (state.currentUnit === episode && state.currentMode === 'meso') {
                bracket.classList.add('active');
            }

            const label = document.createElement('div');
            label.className = 'episode-bracket-label';
            label.textContent = `Ep${episodeIdx}`;
            label.title = isChunk ? (episode.chunk_description || 'Reasoning chunk') : (episode.HypothesisVerbatim || 'Hypothesis episode');
            bracket.appendChild(label);

            bracket.addEventListener('click', () => {
                selectUnit(episode, 'meso');
            });

            bracketsContainer.appendChild(bracket);
        }
    });
}

function getTierAColorClass(operation) {
    const colorMap = {
        'ORIENT': 'tier-a-orient',
        'OBSERVE_DESCRIBE': 'tier-a-observe',
        'INFERENCE': 'tier-a-compare',
        'COMPARE_CONTRAST': 'tier-a-compare', // Legacy support
        'HYPOTHESIZE': 'tier-a-hypothesize',
        'TEST_SEEK_EVIDENCE': 'tier-a-test',
        'EVALUATE_REVISE': 'tier-a-evaluate',
        'META_COGNITION': 'tier-a-meta',
        'RESPONSE_ENTRY': 'tier-a-response'
    };
    return colorMap[operation] || 'tier-a-uncoded';
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function highlightTranscriptUnit(index, type) {
    // Scroll to and flash the unit
    const highlightedEl = document.querySelector(`[data-unit-index="${index}"][data-unit-type="${type}"]`);
    if (highlightedEl) {
        highlightedEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
        highlightedEl.classList.add('flash');
        setTimeout(() => highlightedEl.classList.remove('flash'), 2000);
    }
}

// ===== UNITS SIDEBAR =====
function updateUnitsSidebar() {
    // Micro units
    const microList = document.getElementById('micro-units-list');
    const microCount = document.getElementById('micro-count');
    microCount.textContent = state.microUnits.length;

    microList.innerHTML = '';
    state.microUnits.forEach((unit, index) => {
        const unitEl = document.createElement('div');
        unitEl.className = 'unit-card micro-unit';

        // Get color class based on operation
        const colorClass = getTierAColorClass(unit.A_operation);

        // Build code badges
        let codeBadges = '';
        if (unit.A_operation) {
            codeBadges += `<span class="code-badge tier-a ${colorClass}">${formatOperationLabel(unit.A_operation)}</span>`;
        }
        if (unit.B_content && unit.B_content.length > 0) {
            unit.B_content.forEach(code => {
                codeBadges += `<span class="code-badge tier-b">${code}</span>`;
            });
        }
        if (unit.step_tag) {
            codeBadges += `<span class="code-badge step-tag">${unit.step_tag}</span>`;
        }

        unitEl.innerHTML = `
            <div class="unit-card-header">
                <span class="unit-number ${colorClass}">Turn ${index}</span>
                <button class="delete-unit-btn" data-index="${index}" data-type="micro" title="Delete this turn">×</button>
            </div>
            <div class="unit-card-text">${escapeHtml(unit.raw_text)}</div>
            <div class="unit-card-codes">${codeBadges || '<span class="no-codes">No codes applied</span>'}</div>
        `;

        // Click on card to select
        unitEl.addEventListener('click', (e) => {
            if (!e.target.classList.contains('delete-unit-btn')) {
                selectUnit(unit, 'micro');
            }
        });

        // Delete button handler
        const deleteBtn = unitEl.querySelector('.delete-unit-btn');
        deleteBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            if (confirm(`Delete Turn ${index}?`)) {
                state.microUnits.splice(index, 1);
                state.isDirty = true;
                renderTranscript();
                updateUnitsSidebar();
                if (state.currentUnit === unit) {
                    state.currentUnit = null;
                    updateCurrentUnitInfo();
                }
            }
        });

        microList.appendChild(unitEl);
    });

    // Meso units
    const mesoList = document.getElementById('meso-units-list');
    const mesoCount = document.getElementById('meso-count');
    mesoCount.textContent = state.mesoUnits.length;

    mesoList.innerHTML = '';
    state.mesoUnits.forEach((unit, index) => {
        const unitEl = document.createElement('div');
        unitEl.className = 'unit-card meso-unit';

        // Determine display content based on episode type
        const isChunk = unit.episode_type === 'reasoning_chunk';
        let typeLabel, mainText, allBadges = '';

        if (isChunk) {
            typeLabel = '<span class="episode-type-badge chunk">Reasoning Chunk</span>';
            const chunkTypeLabels = {
                'exploratory_observation': 'Exploratory',
                'hypothesis_flow': 'Hypothesis Flow',
                'testing_sequence': 'Testing',
                'evaluation_period': 'Evaluation'
            };
            const chunkLabel = chunkTypeLabels[unit.chunk_type] || unit.chunk_type || 'Unspecified';
            mainText = `<strong>${chunkLabel}:</strong> ${escapeHtml((unit.chunk_description || 'No description').substring(0, 80))}`;
            if (unit.chunk_description && unit.chunk_description.length > 80) mainText += '...';
        } else {
            typeLabel = '<span class="episode-type-badge hypothesis">Hypothesis Episode</span>';
            mainText = `<strong>Hyp:</strong> ${escapeHtml((unit.HypothesisVerbatim || 'No hypothesis').substring(0, 80))}`;
            if (unit.HypothesisVerbatim && unit.HypothesisVerbatim.length > 80) mainText += '...';
        }

        const spanText = `Turns ${unit.turn_span_start}→${unit.turn_span_end}`;

        // Build comprehensive badge list for all episode metadata
        const badges = [];

        // Hypothesis episode specific badges
        if (!isChunk) {
            if (unit.Outcome) badges.push(`<span class="code-badge outcome">${unit.Outcome}</span>`);
            if (unit.Confidence) badges.push(`<span class="code-badge confidence">${unit.Confidence}</span>`);
            if (unit.EvidenceCited) badges.push(`<span class="code-badge evidence">${unit.EvidenceCited}</span>`);
            if (unit.DistanceToTruth) badges.push(`<span class="code-badge distance">${unit.DistanceToTruth}</span>`);
            if (unit.FeatureBundle && unit.FeatureBundle.length > 0) {
                badges.push(`<span class="code-badge features">Features: ${unit.FeatureBundle.join(', ')}</span>`);
            }
        }

        // Strategy codes (available for both types)
        if (unit.StrategyCodes && unit.StrategyCodes.length > 0) {
            unit.StrategyCodes.forEach(code => {
                const shortCode = code.split('_')[1] || code;
                badges.push(`<span class="code-badge strategy">${shortCode}</span>`);
            });
        }

        allBadges = badges.join('');

        unitEl.innerHTML = `
            <div class="unit-card-header">
                <span class="unit-number episode-number">Episode ${index}</span>
                <button class="delete-unit-btn" data-index="${index}" data-type="meso" title="Delete this episode">×</button>
            </div>
            <div style="margin-bottom: 0.5rem;">
                ${typeLabel}
                <span class="code-badge tier-b">${spanText}</span>
            </div>
            <div class="unit-card-text">${mainText}</div>
            ${allBadges ? `<div class="unit-card-codes">${allBadges}</div>` : ''}
        `;

        unitEl.addEventListener('click', (e) => {
            if (!e.target.classList.contains('delete-unit-btn')) {
                selectUnit(unit, 'meso');
            }
        });

        const deleteBtn = unitEl.querySelector('.delete-unit-btn');
        deleteBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            if (confirm(`Delete Episode ${index}?`)) {
                state.mesoUnits.splice(index, 1);
                state.isDirty = true;
                updateUnitsSidebar();
                updateMacroAnalysis(); // Update macro when episodes change
                if (state.currentUnit === unit) {
                    state.currentUnit = null;
                    updateCurrentUnitInfo();
                }
            }
        });

        mesoList.appendChild(unitEl);
    });

    // Update macro analysis whenever units change
    updateMacroAnalysis();
}

function formatOperationLabel(operation) {
    const labels = {
        'ORIENT': 'Orient',
        'OBSERVE_DESCRIBE': 'Observe',
        'INFERENCE': 'Inference',
        'COMPARE_CONTRAST': 'Compare', // Legacy support
        'HYPOTHESIZE': 'Hypothesize',
        'TEST_SEEK_EVIDENCE': 'Test',
        'EVALUATE_REVISE': 'Evaluate',
        'META_COGNITION': 'Meta',
        'RESPONSE_ENTRY': 'Response'
    };
    return labels[operation] || operation;
}

function selectUnit(unit, type) {
    state.currentUnit = unit;
    state.currentMode = type;
    updateCurrentUnitInfo();

    if (type === 'micro') {
        switchMode('micro');
        populateMicroForm(unit);
    } else if (type === 'meso') {
        switchMode('meso');
        populateEpisodeForm(unit);
    }
}

// ===== CURRENT UNIT INFO =====
function updateCurrentUnitInfo() {
    const unitInfo = document.getElementById('current-unit-info');
    const badge = unitInfo.querySelector('.unit-badge');
    const preview = unitInfo.querySelector('.unit-text-preview');

    if (!state.currentUnit) {
        badge.textContent = 'No unit selected';
        preview.textContent = '';
        return;
    }

    if (state.currentMode === 'micro') {
        badge.textContent = `Micro Unit — Turn ${state.currentUnit.turn_index}`;
        preview.textContent = state.currentUnit.raw_text;
    } else if (state.currentMode === 'meso') {
        badge.textContent = `Meso Unit — Episode ${state.currentUnit.episode_index}`;
        preview.textContent = state.currentUnit.HypothesisVerbatim;
    }
}

// ===== MODE TOGGLE =====
function setupModeToggle() {
    const modeButtons = document.querySelectorAll('.mode-btn');
    modeButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            const mode = btn.dataset.mode;
            switchMode(mode);
        });
    });
}

function switchMode(mode) {
    state.currentMode = mode;

    // Update button states
    document.querySelectorAll('.mode-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.mode === mode);
    });

    // Show correct panel
    document.querySelectorAll('.coding-panel-content').forEach(panel => {
        panel.classList.remove('active');
    });

    document.getElementById(`panel-${mode}`).classList.add('active');

    // Update workflow
    updateWorkflowGuide(mode);
}

function updateWorkflowGuide(mode) {
    // Update workflow steps based on mode
    // This is placeholder - will be enhanced
}

// ===== MICRO CODING (TIER A, STEP TAGS, TIER B) =====
function setupCodingPanels() {
    // Tier A: Operations
    document.querySelectorAll('.btn-select-op').forEach(btn => {
        btn.addEventListener('click', () => {
            const code = btn.dataset.code;
            selectOperationCode(code);
        });
    });

    // Step Tags
    document.querySelectorAll('.step-tag-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const code = btn.dataset.code;
            if (code) {
                toggleStepTag(code);
            }
        });
    });

    document.getElementById('btn-clear-step').addEventListener('click', () => {
        clearStepTag();
    });

    // Apply button
    document.getElementById('btn-apply-micro').addEventListener('click', applyMicroCodes);

    // Clear form button
    document.getElementById('btn-clear-form').addEventListener('click', clearCodingForm);

    // Episode form
    setupEpisodeForm();
}

function selectOperationCode(code) {
    if (!state.currentUnit || state.currentMode !== 'micro') {
        alert('Please select a micro unit (turn) first');
        return;
    }

    // Highlight selected operation
    document.querySelectorAll('.operation-card').forEach(card => {
        card.classList.toggle('selected', card.dataset.code === code);
    });

    state.currentUnit.A_operation = code;
}

function toggleStepTag(code) {
    if (!state.currentUnit || state.currentMode !== 'micro') {
        alert('Please select a micro unit (turn) first');
        return;
    }

    // Toggle step tag
    document.querySelectorAll('.step-tag-btn').forEach(btn => {
        btn.classList.remove('active');
    });

    const btn = document.querySelector(`.step-tag-btn[data-code="${code}"]`);
    if (state.currentUnit.step_tag === code) {
        state.currentUnit.step_tag = null;
    } else {
        state.currentUnit.step_tag = code;
        btn.classList.add('active');
    }
}

function clearStepTag() {
    if (!state.currentUnit || state.currentMode !== 'micro') return;

    state.currentUnit.step_tag = null;
    document.querySelectorAll('.step-tag-btn').forEach(btn => {
        btn.classList.remove('active');
    });
}

function applyMicroCodes() {
    if (!state.currentUnit || state.currentMode !== 'micro') {
        alert('Please select a micro unit (turn) first');
        return;
    }

    // Collect Tier B codes
    const tierBCodes = [];

    // Feature families
    document.querySelectorAll('.b-checkbox-group input[type="checkbox"]:checked').forEach(cb => {
        tierBCodes.push(cb.value);
    });

    // Polarity
    const polarityRadio = document.querySelector('input[name="polarity"]:checked');
    if (polarityRadio) tierBCodes.push(polarityRadio.value);

    // Evidence type
    const evidenceRadio = document.querySelector('input[name="evidence-type"]:checked');
    if (evidenceRadio) tierBCodes.push(evidenceRadio.value);

    // Abstraction
    const abstractionRadio = document.querySelector('input[name="abstraction"]:checked');
    if (abstractionRadio) tierBCodes.push(abstractionRadio.value);

    // Confidence
    const confidenceRadio = document.querySelector('input[name="confidence"]:checked');
    if (confidenceRadio) tierBCodes.push(confidenceRadio.value);

    // Meta Type (B7)
    const metaTypeRadio = document.querySelector('input[name="meta-type"]:checked');
    if (metaTypeRadio) tierBCodes.push(metaTypeRadio.value);

    // Error types
    document.querySelectorAll('.b-checkbox-group input[data-code^="ERROR_"]:checked').forEach(cb => {
        tierBCodes.push(cb.value);
    });

    state.currentUnit.B_content = tierBCodes;

    // Save notes
    const notesField = document.getElementById('micro-notes');
    if (notesField) {
        state.currentUnit.notes = notesField.value || '';
    }

    state.snapshot();
    renderTranscript(); // Re-render to update colors
    updateUnitsSidebar();

    alert('Codes applied successfully!');
}

function clearCodingForm() {
    // Clear Tier A selection
    document.querySelectorAll('.operation-card').forEach(card => {
        card.classList.remove('selected');
    });

    // Clear step tag selection
    document.querySelectorAll('.step-tag-btn').forEach(btn => {
        btn.classList.remove('active');
    });

    // Clear all Tier B checkboxes
    document.querySelectorAll('.b-checkbox-group input[type="checkbox"]').forEach(cb => {
        cb.checked = false;
    });

    // Clear all Tier B radio buttons
    document.querySelectorAll('.b-radio-group input[type="radio"]').forEach(radio => {
        radio.checked = false;
    });

    // Clear notes
    const notesField = document.getElementById('micro-notes');
    if (notesField) {
        notesField.value = '';
    }

    console.log('Coding form cleared');
}

function populateMicroForm(unit) {
    // Select operation
    document.querySelectorAll('.operation-card').forEach(card => {
        card.classList.toggle('selected', card.dataset.code === unit.A_operation);
    });

    // Select step tag
    document.querySelectorAll('.step-tag-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.code === unit.step_tag);
    });

    // Clear all Tier B selections
    document.querySelectorAll('.b-checkbox-group input[type="checkbox"]').forEach(cb => {
        cb.checked = false;
    });
    document.querySelectorAll('.b-radio-group input[type="radio"]').forEach(radio => {
        radio.checked = false;
    });

    // Set Tier B codes
    if (unit.B_content && Array.isArray(unit.B_content)) {
        unit.B_content.forEach(code => {
            const checkbox = document.querySelector(`.b-checkbox-group input[value="${code}"]`);
            if (checkbox) checkbox.checked = true;

            const radio = document.querySelector(`.b-radio-group input[value="${code}"]`);
            if (radio) radio.checked = true;
        });
    }

    // Load notes
    const notesField = document.getElementById('micro-notes');
    if (notesField) {
        notesField.value = unit.notes || '';
    }
}

// ===== EPISODE FORM (MESO) =====
function setupEpisodeForm() {
    document.getElementById('btn-add-feature').addEventListener('click', addFeatureToken);
    document.getElementById('btn-calculate-distance').addEventListener('click', calculateDistance);
    document.getElementById('btn-save-episode').addEventListener('click', saveEpisode);
    document.getElementById('btn-new-episode').addEventListener('click', newEpisode);
    document.getElementById('btn-delete-episode').addEventListener('click', deleteEpisode);
}

function populateEpisodeForm(episode) {
    // Shared fields
    document.getElementById('meso-start').value = episode.turn_span_start || '';
    document.getElementById('meso-end').value = episode.turn_span_end || '';
    document.getElementById('meso-notes').value = episode.Notes || '';

    // Episode type
    const episodeType = episode.episode_type || 'hypothesis_episode';
    const typeRadio = document.getElementById(episodeType === 'hypothesis_episode' ? 'type-hypothesis' : 'type-chunk');
    if (typeRadio) typeRadio.checked = true;

    // Show/hide appropriate fields
    toggleEpisodeFields(episodeType);

    if (episodeType === 'reasoning_chunk') {
        // Populate chunk fields
        document.getElementById('chunk-type').value = episode.chunk_type || '';
        document.getElementById('chunk-description').value = episode.chunk_description || '';
    } else {
        // Populate hypothesis fields
        document.getElementById('meso-hypothesis').value = episode.HypothesisVerbatim || '';
        document.getElementById('meso-evidence').value = episode.EvidenceCited || '';
        document.getElementById('meso-confidence').value = episode.Confidence || '';
        document.getElementById('meso-outcome').value = episode.Outcome || '';
        document.getElementById('meso-distance').value = episode.DistanceToTruth || '';

        // Feature bundle
        renderFeatureTokens(episode.FeatureBundle || []);

        // Strategy codes
        document.querySelectorAll('.strategy-checkbox').forEach(cb => {
            cb.checked = (episode.StrategyCodes || []).includes(cb.value);
        });
    }
}

function toggleEpisodeFields(episodeType) {
    const chunkFields = document.getElementById('chunk-fields');
    const hypothesisFields = document.getElementById('hypothesis-fields');

    if (episodeType === 'reasoning_chunk') {
        chunkFields.style.display = 'block';
        hypothesisFields.style.display = 'none';
    } else {
        chunkFields.style.display = 'none';
        hypothesisFields.style.display = 'block';
    }
}

function renderFeatureTokens(featureBundle) {
    const list = document.getElementById('feature-tokens-list');
    list.innerHTML = '';

    featureBundle.forEach((feature, index) => {
        const token = document.createElement('div');
        token.className = 'feature-token';
        token.innerHTML = `
            <span>${feature}</span>
            <button onclick="removeFeatureToken(${index})">×</button>
        `;
        list.appendChild(token);
    });
}

function addFeatureToken() {
    const feature = prompt('Enter feature (format: family=value, e.g., color=blue):');
    if (feature && feature.includes('=')) {
        if (!state.currentUnit || state.currentMode !== 'meso') return;

        state.currentUnit.FeatureBundle.push(feature);
        renderFeatureTokens(state.currentUnit.FeatureBundle);
    }
}

window.removeFeatureToken = function(index) {
    if (!state.currentUnit || state.currentMode !== 'meso') return;

    state.currentUnit.FeatureBundle.splice(index, 1);
    renderFeatureTokens(state.currentUnit.FeatureBundle);
};

function calculateDistance() {
    if (!state.currentUnit || state.currentMode !== 'meso') {
        alert('Please select an episode first');
        return;
    }

    if (!state.sceneKey) {
        alert('No ground truth available for this scene');
        return;
    }

    const episodeFeatures = state.currentUnit.FeatureBundle;
    const groundTruthFeatures = state.sceneKey.KeyFeatures.split(';');

    // Parse ground truth
    const gtFamilies = {};
    groundTruthFeatures.forEach(f => {
        const [family, value] = f.split('=');
        gtFamilies[family] = value;
    });

    // Parse episode features
    const epFamilies = {};
    episodeFeatures.forEach(f => {
        const [family, value] = f.split('=');
        epFamilies[family] = value;
    });

    // Calculate distance
    const gtKeys = Object.keys(gtFamilies);
    const epKeys = Object.keys(epFamilies);

    // Exact match: all GT families present with correct values
    const exactMatch = gtKeys.every(k => epFamilies[k] === gtFamilies[k]);
    if (exactMatch && gtKeys.length === epKeys.length) {
        state.currentUnit.DistanceToTruth = 'ExactMatch';
        document.getElementById('meso-distance').value = 'ExactMatch';
        showDistanceBreakdown('ExactMatch', 'All required features match exactly!');
        return;
    }

    // Family match partial: at least one GT family present
    const hasOverlap = gtKeys.some(k => k in epFamilies);
    const hasMissingKey = gtKeys.some(k => !(k in epFamilies));

    if (hasOverlap && hasMissingKey) {
        state.currentUnit.DistanceToTruth = 'FamilyMatch_Partial';
        document.getElementById('meso-distance').value = 'FamilyMatch_Partial';
        showDistanceBreakdown('FamilyMatch_Partial', 'Some correct families, but missing key dimensions.');
        return;
    }

    // Family mismatch: no overlap
    if (!hasOverlap) {
        state.currentUnit.DistanceToTruth = 'FamilyMismatch';
        document.getElementById('meso-distance').value = 'FamilyMismatch';
        showDistanceBreakdown('FamilyMismatch', 'No overlap with required feature families.');
        return;
    }

    // Default to rule form mismatch
    state.currentUnit.DistanceToTruth = 'RuleFormMismatch';
    document.getElementById('meso-distance').value = 'RuleFormMismatch';
    showDistanceBreakdown('RuleFormMismatch', 'Structure mismatch (relational vs atomic).');
}

function showDistanceBreakdown(category, explanation) {
    const breakdown = document.getElementById('distance-breakdown');
    breakdown.innerHTML = `
        <div style="font-weight: 600; color: #92400e; margin-bottom: 0.5rem;">
            ${category}
        </div>
        <div style="color: #78350f;">
            ${explanation}
        </div>
    `;
}

function saveEpisode() {
    if (!state.currentUnit || state.currentMode !== 'meso') {
        alert('Please select an episode first');
        return;
    }

    // Collect shared fields
    state.currentUnit.turn_span_start = parseInt(document.getElementById('meso-start').value) || null;
    state.currentUnit.turn_span_end = parseInt(document.getElementById('meso-end').value) || null;
    state.currentUnit.Notes = document.getElementById('meso-notes').value;

    // Collect strategy codes (shared by both episode types)
    state.currentUnit.StrategyCodes = [];
    document.querySelectorAll('.strategy-checkbox:checked').forEach(cb => {
        state.currentUnit.StrategyCodes.push(cb.value);
    });

    // Get episode type
    const episodeType = document.querySelector('input[name="episode-type"]:checked').value;
    state.currentUnit.episode_type = episodeType;

    if (episodeType === 'reasoning_chunk') {
        // Reasoning chunk fields
        state.currentUnit.chunk_type = document.getElementById('chunk-type').value;
        state.currentUnit.chunk_description = document.getElementById('chunk-description').value;

        // Clear hypothesis-specific fields when saving as chunk
        state.currentUnit.HypothesisVerbatim = '';
        state.currentUnit.FeatureBundle = [];
        state.currentUnit.EvidenceCited = null;
        state.currentUnit.Confidence = null;
        state.currentUnit.Outcome = null;
        state.currentUnit.DistanceToTruth = null;
    } else {
        // Hypothesis episode fields
        state.currentUnit.HypothesisVerbatim = document.getElementById('meso-hypothesis').value;
        state.currentUnit.EvidenceCited = document.getElementById('meso-evidence').value;
        state.currentUnit.Confidence = document.getElementById('meso-confidence').value;
        state.currentUnit.Outcome = document.getElementById('meso-outcome').value;
        state.currentUnit.DistanceToTruth = document.getElementById('meso-distance').value;

        // Clear chunk-specific fields when saving as hypothesis
        state.currentUnit.chunk_type = null;
        state.currentUnit.chunk_description = '';
    }

    state.snapshot();
    updateUnitsSidebar();

    // Clear turn range selection
    clearTurnRangeSelection();

    // Show success message
    alert('Episode saved! Click "New Episode" to code another episode, or click an existing episode in the sidebar to edit it.');
}

function newEpisode() {
    // Clear turn range selection from previous episode
    clearTurnRangeSelection();

    const episodeIndex = state.mesoUnits.length;
    const mesoUnit = {
        episode_id: `${state.participantId}_S${state.scene}_EP${episodeIndex}`,
        episode_index: episodeIndex,
        participant_id: state.participantId,
        scene: state.scene,
        turn_span_start: null,
        turn_span_end: null,
        episode_type: 'hypothesis_episode',  // default to hypothesis episode
        chunk_type: null,
        chunk_description: '',
        HypothesisVerbatim: '',
        FeatureBundle: [],
        EvidenceCited: null,
        Confidence: null,
        Outcome: null,
        StrategyCodes: [],
        DistanceToTruth: null,
        Notes: ''
    };

    state.mesoUnits.push(mesoUnit);
    state.currentUnit = mesoUnit;

    // Clear and populate fresh form
    clearEpisodeForm();
    populateEpisodeForm(mesoUnit);

    state.snapshot();
    updateUnitsSidebar();

    console.log(`Created new episode ${episodeIndex}. Form cleared and ready for coding.`);
}

function deleteEpisode() {
    if (!state.currentUnit || state.currentMode !== 'meso') {
        alert('Please select an episode first');
        return;
    }

    if (!confirm('Delete this episode?')) return;

    const index = state.mesoUnits.indexOf(state.currentUnit);
    if (index > -1) {
        state.mesoUnits.splice(index, 1);
        state.currentUnit = null;

        state.snapshot();
        updateUnitsSidebar();
        updateCurrentUnitInfo();
    }
}

// ===== CATEGORY TOGGLES (Tier B) =====
function setupCategoryToggles() {
    document.querySelectorAll('.b-category-header').forEach(header => {
        header.addEventListener('click', () => {
            const category = header.parentElement;
            category.classList.toggle('collapsed');
        });
    });
}

// ===== KEYBOARD SHORTCUTS =====
function setupKeyboardShortcuts() {
    document.addEventListener('keydown', (e) => {
        // Save: Cmd/Ctrl+S
        if ((e.metaKey || e.ctrlKey) && e.key === 's') {
            e.preventDefault();
            saveAll();
        }

        // Undo: Cmd/Ctrl+Z
        if ((e.metaKey || e.ctrlKey) && e.key === 'z' && !e.shiftKey) {
            e.preventDefault();
            undo();
        }

        // Redo: Cmd/Ctrl+Shift+Z
        if ((e.metaKey || e.ctrlKey) && e.shiftKey && e.key === 'z') {
            e.preventDefault();
            redo();
        }

        // Tier A shortcuts (1-8)
        if (state.currentMode === 'micro' && e.key >= '1' && e.key <= '8') {
            const operations = [
                'ORIENT',
                'OBSERVE_DESCRIBE',
                'COMPARE_CONTRAST',
                'HYPOTHESIZE',
                'TEST_SEEK_EVIDENCE',
                'EVALUATE_REVISE',
                'META_COGNITION',
                'RESPONSE_ENTRY'
            ];
            const code = operations[parseInt(e.key) - 1];
            selectOperationCode(code);
        }
    });
}

// ===== SAVE FUNCTIONALITY =====
function setupSaveButtons() {
    document.getElementById('btn-save-all').addEventListener('click', saveAll);
    document.getElementById('btn-undo').addEventListener('click', undo);
    document.getElementById('btn-redo').addEventListener('click', redo);

    // Autosave every 30 seconds
    setInterval(() => {
        if (state.isDirty) {
            saveAll();
        }
    }, 30000);
}

async function saveAll() {
    const payload = {
        participant_id: state.participantId,
        scene: state.scene,
        micro_units: state.microUnits,
        meso_units: state.mesoUnits
    };

    try {
        const response = await fetch('/api/save-coding', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
        });

        // Read the response body
        const data = await response.json();

        if (response.ok && data.success) {
            state.isDirty = false;
            state.lastSaved = new Date();
            updateSaveStatus();
            console.log(`Saved ${data.turns_saved} turns and ${data.episodes_saved} episodes`);
        } else {
            console.error('Save failed:', response.status, data);
            alert(`Save failed: ${response.status} - ${JSON.stringify(data)}`);
        }
    } catch (error) {
        console.error('Save error:', error);
        alert('Save failed: ' + error.message);
    }
}

function undo() {
    if (state.undo()) {
        updateUnitsSidebar();
        updateCurrentUnitInfo();
        renderTranscript();
    }
}

function redo() {
    if (state.redo()) {
        updateUnitsSidebar();
        updateCurrentUnitInfo();
        renderTranscript();
    }
}

function updateSaveStatus() {
    const status = document.getElementById('save-status');
    if (state.isDirty) {
        status.style.color = '#f59e0b';
        status.textContent = '●';
    } else {
        status.style.color = '#10b981';
        status.textContent = '●';
    }
}

// ===== HELP MODAL =====
function setupHelpModal() {
    document.querySelectorAll('.btn-help').forEach(btn => {
        btn.addEventListener('click', () => {
            const helpTopic = btn.dataset.help;
            showHelpModal(helpTopic);
        });
    });

    document.getElementById('btn-close-help').addEventListener('click', () => {
        document.getElementById('help-modal').classList.remove('active');
    });
}

function showHelpModal(topic) {
    const modal = document.getElementById('help-modal');
    const body = document.getElementById('help-modal-body');

    // Help content for different topics
    const helpContent = {
        'tier-a': `
            <h3>Tier A — Operations (Mutually Exclusive)</h3>
            <p>Select exactly <strong>ONE</strong> operation for each turn. These are the fundamental reasoning operations.</p>

            <h4>Quick Reference:</h4>
            <ul>
                <li><strong>ORIENT (1):</strong> Initial task framing, reading instructions</li>
                <li><strong>OBSERVE_DESCRIBE (2):</strong> Pure description, no inference</li>
                <li><strong>INFERENCE (3):</strong> Pattern-seeking, comparison, preliminary reasoning</li>
                <li><strong>HYPOTHESIZE (4):</strong> Proposes a candidate rule</li>
                <li><strong>TEST_SEEK_EVIDENCE (5):</strong> Checks hypothesis against panels</li>
                <li><strong>EVALUATE_REVISE (6):</strong> Accepts/rejects/revises hypothesis</li>
                <li><strong>META_COGNITION (7):</strong> Reflects on difficulty or strategy</li>
                <li><strong>RESPONSE_ENTRY (8):</strong> Commits final answer</li>
            </ul>

            <h4>Decision Rules:</h4>
            <ul>
                <li>If a turn both proposes AND tests, <strong>split into two turns</strong> if possible</li>
                <li>Use the <strong>dominant function</strong> if you cannot split</li>
                <li>Any claim with "must/always/if" → HYPOTHESIZE</li>
                <li>Just naming panels without inference → OBSERVE_DESCRIBE</li>
                <li>"Panel A has X but Panel B doesn't" or "What's the difference?" → INFERENCE</li>
                <li>When coding INFERENCE with comparisons, use <strong>B3_EvidenceType (Mixed)</strong> to capture cross-panel scope</li>
            </ul>`,
        'tier-b': `
            <h3>Tier B — Content (Multi-Label)</h3>
            <p>Select <strong>ALL that apply</strong>. These codes capture what features are mentioned in hypotheses and evidence.</p>

            <h4>Categories:</h4>
            <ul>
                <li><strong>B1 — Feature Family:</strong> COLOR, SIZE, ORIENTATION, POSITION/RELATION, COUNT</li>
                <li><strong>B2 — Polarity:</strong> Presence, Absence, Conditional</li>
                <li><strong>B3 — Evidence Type:</strong> Positive Cases (lit), Negative Cases (unlit), Mixed</li>
                <li><strong>B4 — Abstraction:</strong> Token (this item), Type (class), Schema (relational)</li>
                <li><strong>B5 — Confidence:</strong> Definite, Hedged, Disavowal</li>
                <li><strong>B6 — Error Type:</strong> Only when clear from text (Perceptual, Overfit, Scope, Attribute)</li>
            </ul>

            <h4>Important Notes:</h4>
            <ul>
                <li>Code what the participant <strong>cites</strong>, not what exists in displays</li>
                <li>Multiple feature families can co-occur (e.g., COLOR_Blue + SIZE_Small)</li>
                <li>Only apply Error Type when the error is <strong>explicit in the text</strong></li>
            </ul>`,
        'tier-b1': `
            <h3>B1 — Feature Family</h3>
            <p>Code <strong>all features</strong> mentioned in the hypothesis or evidence statement.</p>

            <h4>Available Features:</h4>
            <ul>
                <li><strong>COLOR:</strong> Blue, Green, Red</li>
                <li><strong>SIZE:</strong> Small, Large</li>
                <li><strong>ORIENTATION:</strong> Upright, Slanted, Horizontal, Upside Down</li>
                <li><strong>POSITION/RELATION:</strong> Above/Below, Adjacency</li>
                <li><strong>COUNT:</strong> Presence (exists), Exact N (specific number)</li>
            </ul>

            <h4>When to code:</h4>
            <ul>
                <li>Code what the participant <strong>explicitly mentions</strong></li>
                <li>Multiple features can apply (e.g., "blue upright triangle" → COLOR_Blue + ORIENTATION_Upright)</li>
                <li>For tests, code the features being <strong>checked</strong>, not all visible features</li>
            </ul>`,
        'tier-b2': `
            <h3>B2 — Polarity</h3>
            <p>How does the hypothesis frame the feature? <strong>Select one.</strong></p>

            <h4>Options:</h4>
            <ul>
                <li><strong>Presence:</strong> Feature must be there (e.g., "needs a blue triangle")</li>
                <li><strong>Absence:</strong> Feature must NOT be there (e.g., "can't have red")</li>
                <li><strong>Conditional:</strong> If-then logic (e.g., "if it has green, then it needs blue above it")</li>
            </ul>

            <h4>Examples:</h4>
            <ul>
                <li>"The star lights up when there's a blue triangle" → <strong>Presence</strong></li>
                <li>"It doesn't work if there's red" → <strong>Absence</strong></li>
                <li>"If green is upright, then blue must be horizontal" → <strong>Conditional</strong></li>
            </ul>`,
        'tier-b3': `
            <h3>B3 — Evidence Type</h3>
            <p>What kind of evidence does the participant cite? <strong>Select one.</strong></p>

            <h4>Options:</h4>
            <ul>
                <li><strong>Positive Cases:</strong> Uses lit panels (star is yellow/lit)</li>
                <li><strong>Negative Cases:</strong> Uses unlit panels (star is gray/not lit)</li>
                <li><strong>Mixed:</strong> References both lit and unlit panels together <strong>(this captures cross-panel comparison)</strong></li>
            </ul>

            <h4>Important:</h4>
            <ul>
                <li>Code what the participant <strong>cites</strong>, not what exists in the display</li>
                <li>If they say "in the lit panels," code <strong>Positive Cases</strong> even if unlit panels also exist</li>
                <li>When coding <strong>INFERENCE</strong> operations that compare panels, use <strong>Mixed</strong> to capture the cross-panel scope</li>
                <li>Example: "Panel A has red but Panel B doesn't" → INFERENCE + B3_Mixed</li>
            </ul>`,
        'tier-b4': `
            <h3>B4 — Abstraction</h3>
            <p>What level of abstraction does the hypothesis operate at? <strong>Select one.</strong></p>

            <h4>Options:</h4>
            <ul>
                <li><strong>Token:</strong> This specific item (e.g., "this triangle in panel A")</li>
                <li><strong>Type:</strong> A class or category (e.g., "blue triangles" in general)</li>
                <li><strong>Schema:</strong> Relational pattern (e.g., "a blue shape above a green shape")</li>
            </ul>

            <h4>Examples:</h4>
            <ul>
                <li>"This triangle needs to be upright" → <strong>Token</strong></li>
                <li>"All blue triangles are upright" → <strong>Type</strong></li>
                <li>"Blue must be above green" → <strong>Schema</strong> (relational)</li>
            </ul>`,
        'tier-b5': `
            <h3>B5 — Confidence</h3>
            <p>How confident is the participant in their statement? <strong>Select one.</strong></p>

            <h4>Options:</h4>
            <ul>
                <li><strong>Definite:</strong> Unhedged, stated with certainty (e.g., "it has to be blue")</li>
                <li><strong>Hedged:</strong> Uses hedging language (e.g., "maybe it's blue," "I think," "it seems like")</li>
                <li><strong>Disavowal:</strong> Expresses uncertainty or lack of knowledge (e.g., "no idea," "just guessing," "random")</li>
            </ul>

            <h4>Look for markers:</h4>
            <ul>
                <li><strong>Definite:</strong> "must," "has to," "always," "definitely"</li>
                <li><strong>Hedged:</strong> "maybe," "possibly," "I think," "seems," "might"</li>
                <li><strong>Disavowal:</strong> "no clue," "no idea," "random guess," "I don't know"</li>
            </ul>`,
        'tier-b6': `
            <h3>B6 — Error Type (Diagnostic)</h3>
            <p><strong>Only code when error is clear from text.</strong> Do not infer. Can select multiple if applicable.</p>

            <h4>Options:</h4>
            <ul>
                <li><strong>Perceptual:</strong> Misperceives visual features (e.g., calls blue "green")</li>
                <li><strong>Logical Overfit:</strong> Adds unnecessary conjuncts to patch hypothesis (e.g., "blue AND upright AND in top-left")</li>
                <li><strong>Scope Mismatch:</strong> Confuses correlation with causation (e.g., "being in panel A makes it light up")</li>
                <li><strong>Attribute Confusion:</strong> Confuses which feature matters (e.g., thinks position matters when it's actually color)</li>
            </ul>

            <h4>Important:</h4>
            <p>Only apply when the participant's <strong>text explicitly reveals</strong> the error. Do not code based on your knowledge of the ground truth.</p>`,
        'tier-b7': `
            <h3>B7 — Meta Type (For META_COGNITION only)</h3>
            <p><strong>Use only when the Tier A operation is META_COGNITION.</strong> Distinguishes between different types of metacognitive statements.</p>

            <h4>Options (mutually exclusive):</h4>
            <ul>
                <li><strong>Affective:</strong> Emotional responses, expressions of difficulty, frustration, or confusion
                    <ul>
                        <li>Examples: "This is so hard," "I'm confused," "Ugh, I don't understand this"</li>
                        <li>Focus: <em>How the participant feels</em></li>
                    </ul>
                </li>
                <li><strong>Strategic:</strong> Explicit planning statements, strategy articulation, or procedural announcements
                    <ul>
                        <li>Examples: "Let me check all the lit panels first," "I'm going to test each color one by one," "I should compare what's different"</li>
                        <li>Focus: <em>What the participant plans to do</em></li>
                    </ul>
                </li>
                <li><strong>Monitoring:</strong> Self-assessment, progress evaluation, or uncertainty about current state
                    <ul>
                        <li>Examples: "I'm not making progress," "Am I on the right track?," "I think I'm getting closer," "Maybe I'm overthinking this"</li>
                        <li>Focus: <em>How the participant is doing</em></li>
                    </ul>
                </li>
            </ul>

            <h4>Why this matters:</h4>
            <p><strong>Strategic</strong> statements are particularly valuable because they predict what search/testing strategies the participant will use, and help you identify whether participants execute their stated plans.</p>`,

        // Episode panel help
        'episode-type': `
            <h3>Episode Type</h3>
            <p>Choose the appropriate episode type based on what you want to capture:</p>

            <h4>Hypothesis Episode (Detailed Analysis)</h4>
            <ul>
                <li>Use when tracking a <strong>specific hypothesis pursuit</strong></li>
                <li>Captures full details: hypothesis verbatim, feature bundle, evidence, strategy codes, distance to truth</li>
                <li>Example: Participant proposes "small blue cone" rule, tests it on panels, revises to "any blue"</li>
            </ul>

            <h4>Reasoning Chunk (Simple Periods)</h4>
            <ul>
                <li>Use for <strong>general reasoning periods</strong> that don't contain explicit hypotheses</li>
                <li>Only requires: turn range, chunk type, brief description</li>
                <li>Example: Exploratory observation period where participant is still scanning features</li>
                <li>Example: Testing sequence that spans multiple hypothesis iterations</li>
            </ul>`,
        'turn-span': `
            <h3>Turn Span (Turn Range)</h3>
            <p>Specify which coded turns this episode covers.</p>

            <h4>Three Ways to Set Turn Range:</h4>

            <h5>1. Click Turns in Transcript (Recommended)</h5>
            <ul>
                <li><strong>IMPORTANT:</strong> Switch to Meso coding panel first!</li>
                <li><strong>Click</strong> the first turn in the transcript → sets start</li>
                <li><strong>Shift+Click</strong> the last turn → extends range to end</li>
                <li>Selected turns get <strong>orange outline</strong></li>
                <li>Turn range inputs auto-fill immediately!</li>
            </ul>

            <h5>2. Use Auto-Fill Button</h5>
            <ul>
                <li>Click ⚡ <strong>Auto-Fill</strong> button</li>
                <li>Uses your selected turn range (if you clicked turns)</li>
                <li>Falls back to all coded turns if no range selected</li>
            </ul>

            <h5>3. Manual Entry</h5>
            <ul>
                <li>Type turn indices directly (e.g., start=2, end=6)</li>
            </ul>

            <h4>Important Notes:</h4>
            <ul>
                <li>Turn indices are <strong>zero-based</strong> (first turn = 0, second turn = 1, etc.)</li>
                <li>Span is <strong>inclusive</strong>: both start and end turns are included</li>
                <li>Turn selection only works when in <strong>Meso mode</strong></li>
            </ul>

            <h4>Example Workflow:</h4>
            <ol>
                <li>Code turns 2, 3, 4, 5, 6 as OBSERVE, INFERENCE, HYPOTHESIZE, TEST, EVALUATE</li>
                <li>Switch to Meso panel → Click "New Episode"</li>
                <li>Click turn 2 in transcript (turn gets orange outline)</li>
                <li>Shift+Click turn 6 (turns 2-6 all get orange outline)</li>
                <li>Turn span auto-fills with: 2 → 6</li>
                <li>Fill in hypothesis details and save!</li>
            </ol>`,
        'chunk-type': `
            <h3>Chunk Type (For Reasoning Chunks)</h3>
            <p>Categorize what kind of reasoning activity this chunk represents:</p>

            <h4>Options:</h4>
            <ul>
                <li><strong>Exploratory Observation:</strong> Scanning panels, noticing features, no hypothesis yet</li>
                <li><strong>Hypothesis Flow:</strong> Moving through multiple hypothesis ideas fluidly</li>
                <li><strong>Testing Sequence:</strong> Systematically checking panels against ideas</li>
                <li><strong>Evaluation Period:</strong> Reflecting on results, comparing hypotheses, meta-reasoning</li>
            </ul>`,
        'chunk-description': `
            <h3>Chunk Description</h3>
            <p>Briefly summarize what happens in this reasoning chunk.</p>

            <h4>Guidelines:</h4>
            <ul>
                <li>Keep it <strong>concise</strong> (1-2 sentences)</li>
                <li>Focus on <strong>what</strong> the participant is doing, not detailed content</li>
                <li>Example: "Scans all panels noting color and orientation differences"</li>
                <li>Example: "Tests three different size-based rules against positive cases"</li>
            </ul>`,
        'hypothesis-verbatim': `
            <h3>Hypothesis (Verbatim)</h3>
            <p>Copy the <strong>exact words</strong> the participant used to state their hypothesis.</p>

            <h4>Guidelines:</h4>
            <ul>
                <li><strong>Use exact quotes</strong> whenever possible</li>
                <li>If hypothesis is stated across multiple turns, combine them</li>
                <li>If hypothesis is implicit, paraphrase as neutrally as possible</li>
                <li>Include hedges like "maybe," "I think," etc.</li>
            </ul>

            <h4>Examples:</h4>
            <ul>
                <li>Good: "I think it's when there's a small blue cone"</li>
                <li>Good: "Maybe it has to have red and be upright"</li>
                <li>Avoid: "They thought blue was important" (not verbatim)</li>
            </ul>`,
        'feature-bundle': `
            <h3>Feature Bundle</h3>
            <p>Extract the <strong>feature-family=value</strong> pairs from the hypothesis.</p>

            <h4>Format:</h4>
            <ul>
                <li>family=value (e.g., color=blue, size=small)</li>
                <li>Use <strong>feature-family granularity</strong> (not specific values)</li>
                <li>Common families: color, size, orientation, position_rel, count</li>
            </ul>

            <h4>Examples:</h4>
            <ul>
                <li>Hypothesis: "small blue cone" → [color=blue, size=small]</li>
                <li>Hypothesis: "two upright triangles" → [count=two, orientation=upright]</li>
                <li>Hypothesis: "red above green" → [color=red, color=green, position_rel=above_below]</li>
            </ul>`,
        'evidence-cited': `
            <h3>Evidence Cited</h3>
            <p>What kind of panel evidence does the participant reference?</p>

            <h4>Options:</h4>
            <ul>
                <li><strong>PositiveCases:</strong> Only cites lit panels ("Panel A has this...")</li>
                <li><strong>NegativeCases:</strong> Only cites unlit panels ("Panel B doesn't have...")</li>
                <li><strong>Mixed:</strong> Cites both lit and unlit panels together in comparison</li>
            </ul>

            <h4>Note:</h4>
            <p>This code captures <strong>cross-panel comparison scope</strong> when set to Mixed.</p>`,
        'confidence': `
            <h3>Confidence</h3>
            <p>How certain is the participant about this hypothesis?</p>

            <h4>Options:</h4>
            <ul>
                <li><strong>Definite:</strong> Unhedged language ("it is," "it has," "the rule is")</li>
                <li><strong>Hedged:</strong> Hedges present ("I think," "maybe," "seems like," "probably")</li>
                <li><strong>Disavowal:</strong> States they don't know ("no idea," "random guess," "can't figure it out")</li>
            </ul>`,
        'outcome': `
            <h3>Outcome</h3>
            <p>What happened to this hypothesis by the end of the episode?</p>

            <h4>Options:</h4>
            <ul>
                <li><strong>Accepted:</strong> Kept as final answer or moved forward confidently</li>
                <li><strong>Revised:</strong> Modified/refined (added/removed features)</li>
                <li><strong>Rejected:</strong> Explicitly abandoned or contradicted</li>
                <li><strong>Pending:</strong> Left unresolved (no clear outcome yet)</li>
            </ul>`,
        'tier-c-strategy': `
            <h3>Tier C — Strategy Codes</h3>
            <p>Episode-level patterns. Select all that apply.</p>

            <h4>Categories:</h4>
            <ul>
                <li><strong>Search Mode:</strong> How they explore the problem space</li>
                <li><strong>Hypothesis Management:</strong> How they handle multiple ideas</li>
                <li><strong>Evidence Policy:</strong> How they gather/use evidence</li>
                <li><strong>Complexity:</strong> Type of rule structure</li>
                <li><strong>Cross-Scene:</strong> Patterns across scenes (transfer/perseveration/adaptation)</li>
            </ul>`,
        'strategy-search-mode': `
            <h3>Search Mode</h3>
            <p>Captures how the participant explores the problem space along two dimensions: <strong>features</strong> (what attributes they attend to) and <strong>panels</strong> (how they move through stimuli).</p>
            <ul>
                <li><strong>featureBreadth:</strong> Scans many different features quickly without deep commitment to any single one</li>
                <li><strong>panelBreadth:</strong> Moves across many panels/stimuli quickly (e.g., "A has X, B has Y, C has Z...")</li>
                <li><strong>featureDepth:</strong> Locks onto one specific feature and explores it thoroughly across panels</li>
                <li><strong>panelDepth:</strong> Examines a single panel or small subset deeply before moving to others</li>
            </ul>
            <p><em>Note: These can co-occur. For example, featureBreadth + panelDepth means exploring many features within a single panel.</em></p>`,
        'strategy-hypothesis-management': `
            <h3>Hypothesis Management</h3>
            <ul>
                <li><strong>SingleTrack:</strong> Pursues one idea at a time</li>
                <li><strong>Parallel:</strong> Holds multiple competing hypotheses simultaneously</li>
                <li><strong>Elimination:</strong> Systematically rules out alternatives</li>
            </ul>`,
        'strategy-evidence-policy': `
            <h3>Evidence Policy</h3>
            <ul>
                <li><strong>ConfirmOnly:</strong> Seeks only confirming cases (lit panels)</li>
                <li><strong>Contrastive:</strong> Deliberately compares lit vs unlit panels</li>
                <li><strong>Falsification:</strong> Actively seeks counterexamples to test hypothesis</li>
            </ul>`,
        'strategy-complexity': `
            <h3>Complexity</h3>
            <ul>
                <li><strong>Atomic:</strong> Simple single-feature rules (e.g., "has blue")</li>
                <li><strong>Conjunctive:</strong> Multiple features combined (e.g., "blue AND small")</li>
                <li><strong>Relational:</strong> Spatial/relational rules (e.g., "red above green," "stacked cones")</li>
            </ul>`,
        'strategy-cross-scene': `
            <h3>Cross-Scene Patterns</h3>
            <ul>
                <li><strong>Transfer:</strong> Successfully reuses a feature family from a prior scene</li>
                <li><strong>Perseveration:</strong> Recycles a previously wrong idea from a prior scene</li>
                <li><strong>AdaptiveShift:</strong> Adjusts strategy appropriately based on prior experience</li>
            </ul>`,
        'distance-to-truth': `
            <h3>Distance to Truth</h3>
            <p>Compare the hypothesis's feature bundle to the ground truth at <strong>feature-family granularity</strong>.</p>

            <h4>Options:</h4>
            <ul>
                <li><strong>ExactMatch:</strong> All required feature families present and correct</li>
                <li><strong>FamilyMatch_Partial:</strong> At least one correct family, but missing key dimension(s)</li>
                <li><strong>FamilyMismatch:</strong> No overlap with ground truth families</li>
                <li><strong>RuleFormMismatch:</strong> Wrong structure (e.g., atomic vs relational)</li>
            </ul>

            <h4>Use Auto-Calculate button:</h4>
            <p>Automatically compares the feature bundle to the scene's ground truth.</p>`
    };

    body.innerHTML = helpContent[topic] || `<p>Help content for ${topic} not yet available.</p>`;
    modal.classList.add('active');
}

// ===== EPISODE TYPE TOGGLE =====
function setupEpisodeTypeToggle() {
    const typeRadios = document.querySelectorAll('input[name="episode-type"]');
    typeRadios.forEach(radio => {
        radio.addEventListener('change', (e) => {
            toggleEpisodeFields(e.target.value);
        });
    });
}

// ===== AUTO-FILL SPAN =====
function setupAutoFillSpan() {
    const btnAutoFill = document.getElementById('btn-autofill-span');
    if (btnAutoFill) {
        btnAutoFill.addEventListener('click', autoFillTurnSpan);
    }
}

function autoFillTurnSpan() {
    if (state.microUnits.length === 0) {
        alert('No coded turns available. Please code some turns first.');
        return;
    }

    let firstTurn, lastTurn;

    // If user has selected a range using shift-click, use that
    if (state.selectedTurnRange.start !== null && state.selectedTurnRange.end !== null) {
        firstTurn = Math.min(state.selectedTurnRange.start, state.selectedTurnRange.end);
        lastTurn = Math.max(state.selectedTurnRange.start, state.selectedTurnRange.end);
    } else {
        // Otherwise use all coded turns
        firstTurn = 0;
        lastTurn = state.microUnits.length - 1;
    }

    // Fill the form
    document.getElementById('meso-start').value = firstTurn;
    document.getElementById('meso-end').value = lastTurn;

    console.log(`Auto-filled turn span: ${firstTurn} → ${lastTurn}`);
}

function clearTurnRangeSelection() {
    // Reset turn range selection state
    state.selectedTurnRange.start = null;
    state.selectedTurnRange.end = null;

    // Remove visual highlight from all turns
    document.querySelectorAll('.highlighted-turn').forEach(el => {
        el.classList.remove('range-selected');
    });

    console.log('Turn range selection cleared');
}

function clearEpisodeForm() {
    // Clear episode type (reset to hypothesis)
    document.getElementById('type-hypothesis').checked = true;
    toggleEpisodeFields('hypothesis_episode');

    // Clear turn span
    document.getElementById('meso-start').value = '';
    document.getElementById('meso-end').value = '';

    // Clear chunk fields
    document.getElementById('chunk-type').value = '';
    document.getElementById('chunk-description').value = '';

    // Clear hypothesis fields
    document.getElementById('meso-hypothesis').value = '';
    document.getElementById('meso-evidence').value = '';
    document.getElementById('meso-confidence').value = '';
    document.getElementById('meso-outcome').value = '';
    document.getElementById('meso-distance').value = '';
    document.getElementById('meso-notes').value = '';

    // Clear feature bundle
    const featuresList = document.getElementById('feature-tokens-list');
    if (featuresList) featuresList.innerHTML = '';

    // Clear strategy checkboxes
    document.querySelectorAll('.strategy-checkbox').forEach(cb => {
        cb.checked = false;
    });

    // Clear distance breakdown
    const breakdown = document.getElementById('distance-breakdown');
    if (breakdown) breakdown.innerHTML = '';

    console.log('Episode form cleared');
}

// ===== MACRO ANALYSIS =====
function updateMacroAnalysis() {
    // Update episode count
    const episodesCountEl = document.getElementById('macro-episodes');
    if (episodesCountEl) {
        episodesCountEl.textContent = state.mesoUnits.length;
    }

    // Calculate average episode length
    const avgLengthEl = document.getElementById('macro-avg-length');
    if (avgLengthEl && state.mesoUnits.length > 0) {
        const totalLength = state.mesoUnits.reduce((sum, ep) => {
            return sum + (ep.turn_span_end - ep.turn_span_start + 1);
        }, 0);
        const avgLength = (totalLength / state.mesoUnits.length).toFixed(1);
        avgLengthEl.textContent = avgLength + ' turns';
    } else if (avgLengthEl) {
        avgLengthEl.textContent = '0';
    }

    // Find dominant strategy
    const strategyEl = document.getElementById('macro-strategy');
    if (strategyEl) {
        const strategyCounts = {};
        state.mesoUnits.forEach(ep => {
            if (ep.StrategyCodes && Array.isArray(ep.StrategyCodes)) {
                ep.StrategyCodes.forEach(code => {
                    strategyCounts[code] = (strategyCounts[code] || 0) + 1;
                });
            }
        });

        if (Object.keys(strategyCounts).length > 0) {
            const dominantStrategy = Object.entries(strategyCounts)
                .sort((a, b) => b[1] - a[1])[0][0];
            const shortLabel = dominantStrategy.split('_')[1] || dominantStrategy;
            strategyEl.textContent = shortLabel;
        } else {
            strategyEl.textContent = '—';
        }
    }

    // Build comprehensive reasoning timeline
    renderReasoningTimeline();
}

function renderReasoningTimeline() {
    const tbody = document.getElementById('cross-scene-tbody');
    if (!tbody) return;

    tbody.innerHTML = '';

    // Build a comprehensive timeline combining turns and episodes
    const timeline = [];

    // Add all micro units (turns)
    state.microUnits.forEach((turn, idx) => {
        timeline.push({
            type: 'turn',
            index: idx,
            operation: turn.A_operation,
            text: turn.raw_text,
            stepTag: turn.step_tag,
            tierB: turn.B_content || []
        });
    });

    // Add all meso units (episodes)
    state.mesoUnits.forEach((episode, idx) => {
        timeline.push({
            type: 'episode',
            index: idx,
            episodeType: episode.episode_type,
            chunkType: episode.chunk_type,
            chunkDescription: episode.chunk_description,
            hypothesis: episode.HypothesisVerbatim,
            outcome: episode.Outcome,
            confidence: episode.Confidence,
            spanStart: episode.turn_span_start,
            spanEnd: episode.turn_span_end,
            strategies: episode.StrategyCodes || []
        });
    });

    // If we have data, display it
    if (timeline.length === 0) {
        tbody.innerHTML = '<tr><td colspan="3" style="text-align: center; color: var(--text-muted); padding: 2rem;">No coded data yet. Start coding turns and episodes to see analysis here.</td></tr>';
        return;
    }

    // Display Micro Units (Turns) Overview
    const operationCounts = {};
    state.microUnits.forEach(turn => {
        const op = turn.A_operation || 'Uncoded';
        operationCounts[op] = (operationCounts[op] || 0) + 1;
    });

    const operationSequence = state.microUnits
        .filter(t => t.A_operation)
        .map(t => formatOperationLabel(t.A_operation))
        .join(' → ');

    tbody.innerHTML += `
        <tr class="macro-section-header">
            <td colspan="3"><strong>MICRO ANALYSIS — Turns (${state.microUnits.length} total)</strong></td>
        </tr>
        <tr>
            <td><strong>Operation Distribution</strong></td>
            <td colspan="2">
                ${Object.entries(operationCounts)
                    .sort((a, b) => b[1] - a[1])
                    .map(([op, count]) => `${formatOperationLabel(op)}: ${count}`)
                    .join(' • ')}
            </td>
        </tr>
        <tr>
            <td><strong>Reasoning Flow</strong></td>
            <td colspan="2" style="font-size: 0.85rem; line-height: 1.6;">
                ${operationSequence || 'No operations coded yet'}
            </td>
        </tr>
    `;

    // Step tag progression if present
    const stepTagSequence = state.microUnits
        .filter(t => t.step_tag)
        .map(t => t.step_tag.replace('STEP_', ''))
        .join(' → ');

    if (stepTagSequence) {
        tbody.innerHTML += `
            <tr>
                <td><strong>Step Progression</strong></td>
                <td colspan="2" style="font-size: 0.85rem;">
                    ${stepTagSequence}
                </td>
            </tr>
        `;
    }

    // Display Meso Units (Episodes) Overview
    if (state.mesoUnits.length > 0) {
        tbody.innerHTML += `
            <tr class="macro-section-header">
                <td colspan="3"><strong>MESO ANALYSIS — Episodes (${state.mesoUnits.length} total)</strong></td>
            </tr>
        `;

        state.mesoUnits.forEach((episode, idx) => {
            const isChunk = episode.episode_type === 'reasoning_chunk';
            const typeLabel = isChunk ? '📦 Chunk' : '💡 Hypothesis';

            let mainContent, outcomeContent;

            if (isChunk) {
                const chunkLabels = {
                    'exploratory_observation': 'Exploratory Observation',
                    'hypothesis_flow': 'Hypothesis Flow',
                    'testing_sequence': 'Testing Sequence',
                    'evaluation_period': 'Evaluation Period'
                };
                mainContent = `<strong>${chunkLabels[episode.chunk_type] || 'Unspecified'}</strong><br/><em>${escapeHtml(episode.chunk_description || 'No description')}</em>`;
                outcomeContent = `Turns ${episode.turn_span_start}→${episode.turn_span_end}`;
            } else {
                mainContent = escapeHtml((episode.HypothesisVerbatim || 'No hypothesis').substring(0, 80)) + (episode.HypothesisVerbatim && episode.HypothesisVerbatim.length > 80 ? '...' : '');
                const badges = [];
                if (episode.Outcome) badges.push(`<span class="inline-badge outcome">${episode.Outcome}</span>`);
                if (episode.Confidence) badges.push(`<span class="inline-badge">${episode.Confidence}</span>`);
                if (episode.FeatureBundle && episode.FeatureBundle.length > 0) {
                    badges.push(`<span class="inline-badge">Features: ${episode.FeatureBundle.length}</span>`);
                }
                outcomeContent = badges.join(' ') || '—';
            }

            tbody.innerHTML += `
                <tr class="episode-row">
                    <td style="font-weight: 600;">${typeLabel} Ep${idx}</td>
                    <td>${mainContent}</td>
                    <td>${outcomeContent}</td>
                </tr>
            `;

            // Show strategy codes if present
            if (!isChunk && episode.StrategyCodes && episode.StrategyCodes.length > 0) {
                tbody.innerHTML += `
                    <tr class="strategy-detail-row">
                        <td></td>
                        <td colspan="2" style="font-size: 0.85rem; color: var(--text-muted);">
                            Strategy: ${episode.StrategyCodes.map(s => s.split('_')[1] || s).join(', ')}
                        </td>
                    </tr>
                `;
            }
        });
    }
}

// ===== VOICE DICTATION =====
let recognition = null;
let isRecording = false;

function setupVoiceDictation() {
    const btn = document.getElementById('btn-dictate-notes');
    const textarea = document.getElementById('micro-notes');

    if (!btn || !textarea) return;

    // Check browser support for Speech Recognition
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

    if (!SpeechRecognition) {
        btn.style.display = 'none';
        console.warn('Speech Recognition API not supported in this browser');
        return;
    }

    // Initialize recognition
    recognition = new SpeechRecognition();
    recognition.continuous = true; // Keep listening
    recognition.interimResults = true; // Show interim results
    recognition.lang = 'en-US';

    let finalTranscript = '';
    let interimTranscript = '';

    recognition.onstart = () => {
        isRecording = true;
        btn.classList.add('recording');
        btn.title = 'Click to stop dictation';
        console.log('Voice dictation started');
    };

    recognition.onresult = (event) => {
        interimTranscript = '';

        for (let i = event.resultIndex; i < event.results.length; i++) {
            const transcript = event.results[i][0].transcript;

            if (event.results[i].isFinal) {
                finalTranscript += transcript + ' ';
            } else {
                interimTranscript += transcript;
            }
        }

        // Update textarea with current content + new transcription
        const currentText = textarea.value;
        const cursorPos = textarea.selectionStart;

        // If there's existing text and we're not at the end, add space
        const prefix = currentText.substring(0, cursorPos);
        const suffix = currentText.substring(cursorPos);
        const needsSpace = prefix.length > 0 && !prefix.endsWith(' ') && !prefix.endsWith('\n');

        textarea.value = prefix + (needsSpace ? ' ' : '') + finalTranscript + interimTranscript + suffix;

        // Move cursor to end of transcribed text
        const newCursorPos = (prefix + (needsSpace ? ' ' : '') + finalTranscript + interimTranscript).length;
        textarea.setSelectionRange(newCursorPos, newCursorPos);
    };

    recognition.onerror = (event) => {
        console.error('Speech recognition error:', event.error);

        if (event.error === 'not-allowed') {
            alert('Microphone access denied. Please allow microphone access in your browser settings.');
        } else if (event.error === 'no-speech') {
            console.log('No speech detected, continuing...');
        } else {
            alert(`Speech recognition error: ${event.error}`);
        }

        stopDictation();
    };

    recognition.onend = () => {
        if (isRecording) {
            // Recognition stopped unexpectedly, try to restart
            try {
                recognition.start();
            } catch (e) {
                console.log('Could not restart recognition:', e);
                stopDictation();
            }
        } else {
            stopDictation();
        }
    };

    btn.addEventListener('click', () => {
        if (isRecording) {
            stopDictation();
        } else {
            startDictation();
        }
    });

    function startDictation() {
        finalTranscript = '';
        interimTranscript = '';

        try {
            recognition.start();
        } catch (e) {
            console.error('Could not start recognition:', e);
            alert('Could not start voice dictation. Please try again.');
        }
    }

    function stopDictation() {
        isRecording = false;
        btn.classList.remove('recording');
        btn.title = 'Click to start voice dictation';

        try {
            recognition.stop();
        } catch (e) {
            console.log('Recognition already stopped');
        }

        console.log('Voice dictation stopped');
    }
}
