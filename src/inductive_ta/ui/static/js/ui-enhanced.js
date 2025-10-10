/**
 * Enhanced UI JavaScript with advanced features
 * - Undo/Redo functionality
 * - Hypothesis tracking
 * - Timeline visualization
 * - Bulk operations
 * - Performance optimizations
 */

(() => {
  'use strict';

  // ===========================
  // Constants & Configuration
  // ===========================
  const UNDO_STACK_SIZE = 50;
  const AUTOSAVE_INTERVAL = 60000; // 60 seconds
  const DEBOUNCE_DELAY = 300;

  // ===========================
  // State Management
  // ===========================
  class ApplicationState {
    constructor() {
      this.participant = null;
      this.preamble = '';
      this.scenes = [];
      this.activeScene = 0;
      this.highlightHedges = false;
      this.undoStack = [];
      this.redoStack = [];
      this.isDirty = false;
      this.lastSave = null;
      this.analyticsCache = null;
      this.hypothesesCache = null;
    }

    pushHistory() {
      const snapshot = {
        scenes: this.scenes.map(s => ({
          ...s,
          body: s.textarea.value
        })),
        timestamp: Date.now()
      };

      this.undoStack.push(snapshot);
      if (this.undoStack.length > UNDO_STACK_SIZE) {
        this.undoStack.shift();
      }
      this.redoStack = []; // Clear redo stack on new action
      this.isDirty = true;
    }

    undo() {
      if (this.undoStack.length === 0) return false;

      const current = {
        scenes: this.scenes.map(s => ({
          ...s,
          body: s.textarea.value
        })),
        timestamp: Date.now()
      };
      this.redoStack.push(current);

      const previous = this.undoStack.pop();
      this.restoreSnapshot(previous);
      return true;
    }

    redo() {
      if (this.redoStack.length === 0) return false;

      const current = {
        scenes: this.scenes.map(s => ({
          ...s,
          body: s.textarea.value
        })),
        timestamp: Date.now()
      };
      this.undoStack.push(current);

      const next = this.redoStack.pop();
      this.restoreSnapshot(next);
      return true;
    }

    restoreSnapshot(snapshot) {
      snapshot.scenes.forEach((sceneData, idx) => {
        if (this.scenes[idx]) {
          this.scenes[idx].textarea.value = sceneData.body;
          this.scenes[idx].body = sceneData.body;
        }
      });
    }
  }

  // ===========================
  // Utility Functions
  // ===========================
  const debounce = (func, delay) => {
    let timeoutId;
    return (...args) => {
      clearTimeout(timeoutId);
      timeoutId = setTimeout(() => func(...args), delay);
    };
  };

  const throttle = (func, limit) => {
    let inThrottle;
    return (...args) => {
      if (!inThrottle) {
        func(...args);
        inThrottle = true;
        setTimeout(() => inThrottle = false, limit);
      }
    };
  };

  const escapeHtml = (str) => {
    return str
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  };

  const escapeRegex = (str) => {
    return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  };

  // ===========================
  // Main Application
  // ===========================
  document.addEventListener('DOMContentLoaded', () => {
    const participantData = window.PARTICIPANT_DATA;
    if (!participantData) return;

    const spec = window.CODEBOOK_SPEC || {};
    const hedges = (spec.hedges || []).map(token => token.toLowerCase());
    const state = new ApplicationState();

    // DOM Elements
    const elements = {
      scenePanels: Array.from(document.querySelectorAll('.scene-panel')),
      sceneTabs: Array.from(document.querySelectorAll('.scene-tab')),
      previewBody: document.getElementById('preview-body'),
      tagList: document.getElementById('tag-list'),
      saveStatus: document.getElementById('save-status'),
      summaryTotal: document.getElementById('summary-total'),
      summaryStatus: document.getElementById('summary-status'),
      validationMessages: document.getElementById('validation-messages'),
      attrFeatureInputs: Array.from(document.querySelectorAll('.attr-feature')),
      attrPolarity: document.getElementById('attr-polarity'),
      attrEvidence: document.getElementById('attr-evidence'),
      attrAbstraction: document.getElementById('attr-abstraction'),
      attrConfidence: document.getElementById('attr-confidence'),
      attrError: document.getElementById('attr-error'),
      attrTruth: document.getElementById('attr-truth'),
    };

    // Initialize state
    state.participant = participantData.participant_id;
    state.preamble = participantData.preamble || '';
    state.scenes = elements.scenePanels.map((panel, index) => {
      const textarea = panel.querySelector('.scene-text');
      const heading = panel.querySelector('.scene-heading').textContent || '';
      const number = Number(textarea.dataset.sceneNumber || index + 1);
      return {
        index,
        heading,
        number,
        textarea,
        body: textarea.value,
      };
    });

    // ===========================
    // UI Helper Functions
    // ===========================
    const setStatus = (message, type = 'info') => {
      if (!elements.saveStatus) return;
      elements.saveStatus.textContent = message;
      elements.saveStatus.className = `muted status-${type}`;
    };

    const showNotification = (message, type = 'info') => {
      const notification = document.createElement('div');
      notification.className = `notification notification-${type} animate-slide-in`;
      notification.textContent = message;
      notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 1rem 1.5rem;
        background: ${type === 'success' ? 'var(--accent-success)' : type === 'error' ? 'var(--accent-danger)' : 'var(--accent-primary)'};
        color: white;
        border-radius: var(--radius-lg);
        box-shadow: var(--shadow-xl);
        z-index: 10000;
        font-weight: 600;
        max-width: 400px;
      `;
      document.body.appendChild(notification);
      setTimeout(() => {
        notification.style.opacity = '0';
        notification.style.transform = 'translateX(20px)';
        notification.style.transition = 'all 0.3s ease';
        setTimeout(() => notification.remove(), 300);
      }, 3000);
    };

    const getActiveScene = () => state.scenes[state.activeScene];

    const collectAttributes = () => {
      const features = elements.attrFeatureInputs
        .filter(input => input.checked)
        .map(input => input.value.trim())
        .filter(Boolean);

      const attrs = {
        feature: features.join(' '),
        polarity: elements.attrPolarity?.value || '',
        evidence: elements.attrEvidence?.value || '',
        abstraction: elements.attrAbstraction?.value || '',
        confidence: elements.attrConfidence?.value || '',
        error: elements.attrError?.value || '',
        truth_alignment: elements.attrTruth?.value || '',
      };

      Object.keys(attrs).forEach(key => {
        if (!attrs[key]) delete attrs[key];
      });
      return attrs;
    };

    const attrsToString = (attrs) => {
      return Object.entries(attrs)
        .map(([key, value]) => ` ${key}="${value}"`)
        .join('');
    };

    const clearAttributes = () => {
      elements.attrFeatureInputs.forEach(input => input.checked = false);
      if (elements.attrPolarity) elements.attrPolarity.value = '';
      if (elements.attrEvidence) elements.attrEvidence.value = '';
      if (elements.attrAbstraction) elements.attrAbstraction.value = '';
      if (elements.attrConfidence) elements.attrConfidence.value = '';
      if (elements.attrError) elements.attrError.value = '';
      if (elements.attrTruth) elements.attrTruth.value = '';
    };

    // ===========================
    // Tag Wrapping
    // ===========================
    const wrapSelection = (tag) => {
      const scene = getActiveScene();
      if (!scene) return;

      const textarea = scene.textarea;
      textarea.focus();

      const start = textarea.selectionStart;
      const end = textarea.selectionEnd;

      if (start === end) {
        setStatus('Select text before applying a code.', 'error');
        return;
      }

      const value = textarea.value;
      const selected = value.slice(start, end);

      // Enhanced tag nesting detection
      const beforeSelection = value.slice(0, start);
      const openTags = (beforeSelection.match(/<[A-Z_]+[^>]*>/g) || []).length;
      const closeTags = (beforeSelection.match(/<\/[A-Z_]+>/g) || []).length;

      if (openTags !== closeTags) {
        setStatus('Selection starts inside an unclosed tag.', 'error');
        return;
      }

      const attrs = collectAttributes();
      const attrString = attrsToString(attrs);
      const tagText = `<${tag}${attrString}>${selected}</${tag}>`;

      state.pushHistory(); // Save to undo stack

      const nextValue = `${value.slice(0, start)}${tagText}${value.slice(end)}`;
      textarea.value = nextValue;
      textarea.selectionStart = start;
      textarea.selectionEnd = start + tagText.length;

      scene.body = textarea.value;
      renderPreview();
      renderTagList();
      refreshTagTotals();
      clearAttributes(); // Auto-clear after tagging
      setStatus(`Applied ${tag}.`, 'success');

      // Check for incomplete cycles
      checkIncompleteCycles();
    };

    // ===========================
    // Bulk Operations
    // ===========================
    const openBulkFindTag = () => {
      const dialog = document.getElementById('bulk-find-dialog');
      if (!dialog) return;
      dialog.showModal();
    };

    const performBulkTag = (pattern, tag, attrs) => {
      const scene = getActiveScene();
      if (!scene) return;

      state.pushHistory();

      const textarea = scene.textarea;
      const value = textarea.value;
      const regex = new RegExp(pattern, 'gi');
      const matches = [];
      let match;

      while ((match = regex.exec(value)) !== null) {
        matches.push({
          start: match.index,
          end: match.index + match[0].length,
          text: match[0]
        });
      }

      if (matches.length === 0) {
        setStatus('No matches found.', 'info');
        return;
      }

      // Wrap matches in reverse order to maintain positions
      let newValue = value;
      for (let i = matches.length - 1; i >= 0; i--) {
        const m = matches[i];
        const attrString = attrsToString(attrs);
        const tagText = `<${tag}${attrString}>${m.text}</${tag}>`;
        newValue = newValue.slice(0, m.start) + tagText + newValue.slice(m.end);
      }

      textarea.value = newValue;
      scene.body = newValue;
      renderPreview();
      renderTagList();
      refreshTagTotals();
      showNotification(`Tagged ${matches.length} instances`, 'success');
    };

    // ===========================
    // Preview Rendering
    // ===========================
    const highlightPlain = (text) => {
      let escaped = escapeHtml(text);
      if (!state.highlightHedges || hedges.length === 0) {
        return escaped.replace(/\n/g, '<br>');
      }
      hedges.forEach(token => {
        const pattern = new RegExp(`\\b${escapeRegex(token)}\\b`, 'gi');
        escaped = escaped.replace(pattern, match => `<mark class="hedge">${match}</mark>`);
      });
      return escaped.replace(/\n/g, '<br>');
    };

    const parseAttrString = (attrString) => {
      const attrs = {};
      if (!attrString) return attrs;
      const attrPattern = /([a-z_]+)="([^"]*)"/g;
      let match;
      while ((match = attrPattern.exec(attrString)) !== null) {
        attrs[match[1]] = match[2];
      }
      return attrs;
    };

    const renderChips = (attrs) => {
      const chips = [];
      if (attrs.feature) {
        attrs.feature
          .split(/[,\s]+/)
          .filter(Boolean)
          .forEach(token => {
            chips.push(`<span class="tag-chip">${token}</span>`);
          });
      }
      ['polarity', 'evidence', 'abstraction', 'confidence', 'error', 'truth_alignment'].forEach(key => {
        if (attrs[key]) {
          chips.push(`<span class="tag-chip">${key}:${attrs[key]}</span>`);
        }
      });
      return chips.length ? `<span class="tag-chips">${chips.join('')}</span>` : '';
    };

    const renderMarkup = (text) => {
      const tagPattern = /<([A-Z_]+)([^>]*)>([\s\S]*?)<\/\1>/g;
      let html = '';
      let lastIndex = 0;
      let match;

      while ((match = tagPattern.exec(text)) !== null) {
        const before = text.slice(lastIndex, match.index);
        html += highlightPlain(before);

        const tag = match[1];
        const attrs = parseAttrString(match[2]);
        const inner = renderMarkup(match[3]);
        html += `<span class="tag" data-tag="${tag}"><span class="tag-badge">${tag}</span><span class="tag-text">${inner}</span>${renderChips(attrs)}</span>`;
        lastIndex = match.index + match[0].length;
      }

      html += highlightPlain(text.slice(lastIndex));
      return html;
    };

    const renderPreview = throttle(() => {
      const scene = getActiveScene();
      if (!scene || !elements.previewBody) return;
      elements.previewBody.innerHTML = renderMarkup(scene.textarea.value);
    }, 200);

    // ===========================
    // Tag List
    // ===========================
    const listTags = (text) => {
      const pattern = /<([A-Z_]+)([^>]*)>([\s\S]*?)<\/\1>/g;
      const tags = [];
      let match;
      while ((match = pattern.exec(text)) !== null) {
        const snippet = match[3].replace(/\s+/g, ' ').trim().slice(0, 120);
        tags.push({
          tag: match[1],
          attrs: parseAttrString(match[2]),
          snippet,
          position: match.index,
        });
      }
      return tags;
    };

    const renderTagList = () => {
      if (!elements.tagList) return;
      const scene = getActiveScene();
      const tags = listTags(scene.textarea.value);
      elements.tagList.innerHTML = tags
        .map(item => {
          const attrs = Object.entries(item.attrs)
            .map(([key, value]) => `${key}=${value}`)
            .join(', ');
          return `<li><strong>${item.tag}</strong> — ${escapeHtml(item.snippet)}${attrs ? ` <span class="muted">(${escapeHtml(attrs)})</span>` : ''}</li>`;
        })
        .join('');
    };

    // ===========================
    // Analytics & Validation
    // ===========================
    const checkIncompleteCycles = debounce(() => {
      const text = composeDocument();
      fetch('/api/analytics/' + state.participant)
        .then(res => res.json())
        .then(data => {
          if (data.incomplete_cycles && data.incomplete_cycles.length > 0) {
            showNotification(`${data.incomplete_cycles.length} incomplete reasoning cycles detected`, 'warning');
          }
        })
        .catch(() => {});
    }, 2000);

    const loadAnalytics = async () => {
      if (state.analyticsCache) return state.analyticsCache;
      try {
        const res = await fetch('/api/analytics/' + state.participant);
        const data = await res.json();
        state.analyticsCache = data;
        return data;
      } catch (error) {
        console.error('Failed to load analytics:', error);
        return null;
      }
    };

    const loadHypotheses = async () => {
      if (state.hypothesesCache) return state.hypothesesCache;
      try {
        const res = await fetch('/api/hypothesis-graph/' + state.participant);
        const data = await res.json();
        state.hypothesesCache = data;
        return data;
      } catch (error) {
        console.error('Failed to load hypotheses:', error);
        return null;
      }
    };

    const showTimeline = async () => {
      const analytics = await loadAnalytics();
      if (!analytics || !analytics.timeline) return;

      const timeline = analytics.timeline;
      const timelinePanel = document.getElementById('timeline-panel');
      if (!timelinePanel) return;

      // Render timeline visualization
      let html = '<div class="timeline-container">';
      timeline.operations.forEach((op, idx) => {
        html += `
          <div class="timeline-item animate-fade-in" style="animation-delay: ${idx * 0.05}s">
            <div class="timeline-marker scene-${op.scene}"></div>
            <div class="timeline-content">
              <div class="timeline-tag">${op.tag}</div>
              <div class="timeline-snippet">${escapeHtml(op.snippet)}</div>
              ${op.episode ? `<div class="timeline-episode">Episode: ${op.episode}</div>` : ''}
            </div>
          </div>
        `;
      });
      html += '</div>';

      timelinePanel.innerHTML = html;
      timelinePanel.classList.add('visible');
    };

    const showHypothesisGraph = async () => {
      const graph = await loadHypotheses();
      if (!graph) return;

      const graphPanel = document.getElementById('hypothesis-graph-panel');
      if (!graphPanel) return;

      // Render hypothesis graph (simplified version)
      let html = '<div class="hypothesis-graph">';
      html += `<div class="graph-stats">
        <div>Total Hypotheses: <strong>${graph.stats.total_hypotheses}</strong></div>
        <div>Evolution Chains: <strong>${graph.stats.evolution_chains}</strong></div>
        <div>Scenes Covered: <strong>${graph.stats.scenes_covered}</strong></div>
      </div>`;
      html += '<div class="hypothesis-nodes">';
      graph.nodes.forEach(node => {
        html += `
          <div class="hypothesis-node ${node.outcome}">
            <div class="node-scene">Scene ${node.scene}</div>
            <div class="node-episode">${node.episode}</div>
            <div class="node-verbatim">${escapeHtml(node.verbatim)}</div>
            <div class="node-features">${node.features.join(', ')}</div>
          </div>
        `;
      });
      html += '</div></div>';

      graphPanel.innerHTML = html;
      graphPanel.classList.add('visible');
    };

    // ===========================
    // Tag Counting
    // ===========================
    const countAllTags = () => {
      const pattern = /<([A-Z_]+)([^>]*)>/g;
      const counts = {};
      const text = composeDocument();
      let match;
      while ((match = pattern.exec(text)) !== null) {
        const tag = match[1];
        counts[tag] = (counts[tag] || 0) + 1;
      }
      return counts;
    };

    const refreshTagTotals = () => {
      const counts = countAllTags();
      const total = Object.values(counts).reduce((acc, value) => acc + value, 0);
      if (elements.summaryTotal) {
        elements.summaryTotal.textContent = total;
      }
    };

    const composeDocument = () => {
      return (
        (state.preamble || '') +
        state.scenes
          .map(scene => `${scene.heading}${scene.textarea.value}`)
          .join('')
      );
    };

    // ===========================
    // Save & Validation
    // ===========================
    const saveDocument = async () => {
      const payload = {
        preamble: state.preamble,
        scenes: state.scenes.map(scene => ({
          number: scene.number,
          heading: scene.heading,
          body: scene.textarea.value,
        })),
      };

      try {
        const response = await fetch(`/api/save/${state.participant}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });

        const body = await response.json();

        if (!response.ok) {
          throw body;
        }

        setStatus(body.message || 'Saved.', 'success');
        if (elements.summaryStatus) {
          const timestamp = new Date().toLocaleTimeString();
          elements.summaryStatus.textContent = timestamp;
        }
        refreshTagTotals();
        if (elements.validationMessages) {
          elements.validationMessages.innerHTML = '';
        }

        state.isDirty = false;
        state.lastSave = Date.now();
        showNotification('Saved successfully', 'success');

        // Clear analytics cache after save
        state.analyticsCache = null;
        state.hypothesesCache = null;
      } catch (err) {
        const errors = err?.errors || ['Failed to save document.'];
        setStatus(errors[0], 'error');
        showNotification(errors[0], 'error');
      }
    };

    const runValidation = async () => {
      try {
        const response = await fetch('/api/validate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text: composeDocument() }),
        });

        const body = await response.json();

        if (elements.validationMessages) {
          elements.validationMessages.innerHTML = '';
        }

        const errors = body.errors || [];
        if (errors.length === 0) {
          setStatus('Validation passed — no structural issues detected.', 'success');
          showNotification('Validation passed', 'success');
        } else {
          setStatus('Validation found issues.', 'error');
          if (elements.validationMessages) {
            elements.validationMessages.innerHTML = errors.map(e => `<li>${escapeHtml(e)}</li>`).join('');
          }
          showNotification(`${errors.length} validation issues found`, 'error');
        }
      } catch (error) {
        setStatus('Validation failed.', 'error');
        showNotification('Validation failed', 'error');
      }
    };

    // ===========================
    // Episode Block
    // ===========================
    const insertEpisodeBlock = (data) => {
      const scene = getActiveScene();
      if (!scene) return;

      state.pushHistory();

      const textarea = scene.textarea;
      const blockLines = [
        '```episode',
        `participant: ${state.participant}`,
        `scene: ${data.scene || scene.number}`,
        `episode: ${data.episode || 'EP1'}`,
        'strategy:',
        `  search_mode: ${data.search_mode || ''}`,
        `  hypothesis_management: ${data.hypothesis_management || ''}`,
        `  evidence_policy: ${data.evidence_policy || ''}`,
        `complexity: ${data.complexity || ''}`,
        `cross_scene_shift: ${data.cross_scene_shift || ''}`,
        `hypothesis_verbatim: ${data.hypothesis_verbatim || ''}`,
        `feature_bundle: ${data.feature_bundle || ''}`,
        `evidence_cited: ${data.evidence_cited || ''}`,
        `confidence: ${data.confidence || ''}`,
        `outcome: ${data.outcome || ''}`,
        `summary: ${data.summary || ''}`,
        '```',
        '',
      ];
      const text = blockLines.join('\n');
      insertTextAtCursor(textarea, `\n${text}`);
      scene.body = textarea.value;
      renderPreview();
      renderTagList();
      setStatus('Episode block inserted.', 'success');
    };

    const insertTextAtCursor = (textarea, text) => {
      const start = textarea.selectionStart;
      const end = textarea.selectionEnd;
      const value = textarea.value;
      textarea.value = `${value.slice(0, start)}${text}${value.slice(end)}`;
      const cursor = start + text.length;
      textarea.selectionStart = textarea.selectionEnd = cursor;
    };

    // ===========================
    // Event Handlers
    // ===========================

    // Scene switching
    elements.sceneTabs.forEach(tab => {
      tab.addEventListener('click', event => {
        const index = Number(event.currentTarget.dataset.sceneIndex);
        if (Number.isNaN(index)) return;
        state.activeScene = index;
        elements.sceneTabs.forEach(t => t.classList.remove('is-active'));
        elements.scenePanels.forEach(panel => panel.classList.remove('is-active'));
        tab.classList.add('is-active');
        const panel = elements.scenePanels[index];
        panel.classList.add('is-active');
        const textarea = state.scenes[index].textarea;
        textarea.focus();
        renderPreview();
        renderTagList();
      });
    });

    // Textarea input
    state.scenes.forEach(scene => {
      scene.textarea.addEventListener('input', debounce(() => {
        scene.body = scene.textarea.value;
        if (state.scenes[state.activeScene] === scene) {
          renderPreview();
          renderTagList();
        }
        refreshTagTotals();
        state.isDirty = true;
      }, DEBOUNCE_DELAY));
    });

    // Operation buttons
    document.querySelectorAll('.op-btn').forEach(button => {
      button.addEventListener('click', () => {
        const tag = button.dataset.op;
        if (tag) wrapSelection(tag);
      });
    });

    // Save button
    const saveButton = document.getElementById('btn-save');
    if (saveButton) {
      saveButton.addEventListener('click', () => saveDocument());
    }

    // Validate button
    const validateButton = document.getElementById('btn-validate');
    if (validateButton) {
      validateButton.addEventListener('click', () => runValidation());
    }

    // Highlight hedges button
    const highlightButton = document.getElementById('btn-highlight-hedges');
    if (highlightButton) {
      highlightButton.addEventListener('click', () => {
        state.highlightHedges = !state.highlightHedges;
        highlightButton.textContent = state.highlightHedges ? 'Clear hedge highlight' : 'Highlight hedges';
        renderPreview();
      });
    }

    // Clear attributes button
    const clearAttrsButton = document.getElementById('btn-clear-attrs');
    if (clearAttrsButton) {
      clearAttrsButton.addEventListener('click', () => {
        clearAttributes();
        setStatus('Attribute selections cleared.', 'info');
      });
    }

    // Show timeline button
    const timelineButton = document.getElementById('btn-show-timeline');
    if (timelineButton) {
      timelineButton.addEventListener('click', () => showTimeline());
    }

    // Show hypothesis graph button
    const hypothesisButton = document.getElementById('btn-show-hypotheses');
    if (hypothesisButton) {
      hypothesisButton.addEventListener('click', () => showHypothesisGraph());
    }

    // Bulk find and tag button
    const bulkFindButton = document.getElementById('btn-bulk-find');
    if (bulkFindButton) {
      bulkFindButton.addEventListener('click', () => openBulkFindTag());
    }

    // ===========================
    // Keyboard Shortcuts
    // ===========================
    window.addEventListener('keydown', event => {
      // Save: Cmd/Ctrl + S
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 's') {
        event.preventDefault();
        saveDocument();
        return;
      }

      // Undo: Cmd/Ctrl + Z
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'z' && !event.shiftKey) {
        event.preventDefault();
        if (state.undo()) {
          renderPreview();
          renderTagList();
          refreshTagTotals();
          showNotification('Undone', 'info');
        }
        return;
      }

      // Redo: Cmd/Ctrl + Shift + Z or Cmd/Ctrl + Y
      if (((event.metaKey || event.ctrlKey) && event.shiftKey && event.key.toLowerCase() === 'z') ||
          ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'y')) {
        event.preventDefault();
        if (state.redo()) {
          renderPreview();
          renderTagList();
          refreshTagTotals();
          showNotification('Redone', 'info');
        }
        return;
      }

      // Number keys for operations (without modifier keys)
      if (!event.ctrlKey && !event.metaKey && !event.altKey) {
        const keyMap = {
          Digit1: 'OBSERVE_DESCRIBE',
          Digit2: 'COMPARE_CONTRAST',
          Digit3: 'HYPOTHESIZE',
          Digit4: 'TEST_SEEK_EVIDENCE',
          Digit5: 'EVALUATE_REVISE',
          Digit6: 'META_COGNITION',
          Digit7: 'RESPONSE_ENTRY',
        };
        const tag = keyMap[event.code];
        if (tag) {
          event.preventDefault();
          wrapSelection(tag);
        }
      }
    });

    // ===========================
    // Episode Dialog
    // ===========================
    const episodeDialog = document.getElementById('episode-dialog');
    const episodeForm = document.getElementById('episode-form');
    const episodeButton = document.getElementById('btn-insert-episode');

    if (episodeDialog && episodeForm && episodeButton) {
      episodeButton.addEventListener('click', () => {
        const scene = getActiveScene();
        episodeForm.reset();
        const sceneField = episodeForm.elements.namedItem('scene');
        if (sceneField) {
          sceneField.value = scene.number;
        }

        // Pre-fill with selected text if available
        const textarea = scene.textarea;
        const selection = textarea.value.slice(textarea.selectionStart, textarea.selectionEnd);
        if (selection) {
          const verbatimField = episodeForm.elements.namedItem('hypothesis_verbatim');
          if (verbatimField) {
            verbatimField.value = selection;
          }
        }

        episodeDialog.showModal();
      });

      episodeDialog.addEventListener('close', () => {
        if (episodeDialog.returnValue !== 'confirm') return;
        const formData = new FormData(episodeForm);
        const data = Object.fromEntries(formData.entries());
        insertEpisodeBlock(data);
      });
    }

    // ===========================
    // Autosave
    // ===========================
    setInterval(() => {
      if (state.isDirty && state.lastSave && (Date.now() - state.lastSave > AUTOSAVE_INTERVAL)) {
        saveDocument();
      }
    }, AUTOSAVE_INTERVAL);

    // Warn before closing with unsaved changes
    window.addEventListener('beforeunload', event => {
      if (state.isDirty) {
        event.preventDefault();
        event.returnValue = '';
      }
    });

    // ===========================
    // Initial Render
    // ===========================
    renderPreview();
    renderTagList();
    refreshTagTotals();

    console.log('Enhanced UI initialized successfully');
  });
})();
