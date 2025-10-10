(() => {
  document.addEventListener('DOMContentLoaded', () => {
    const participantData = window.PARTICIPANT_DATA;
    if (!participantData) {
      return;
    }

    const spec = window.CODEBOOK_SPEC || {};
    const hedges = (spec.hedges || []).map((token) => token.toLowerCase());

    const state = {
      participant: participantData.participant_id,
      preamble: participantData.preamble || '',
      scenes: [],
      activeScene: 0,
      highlightHedges: false,
    };

    const scenePanels = Array.from(document.querySelectorAll('.scene-panel'));
    const sceneTabs = Array.from(document.querySelectorAll('.scene-tab'));
    const previewBody = document.getElementById('preview-body');
    const tagList = document.getElementById('tag-list');
    const saveStatus = document.getElementById('save-status');
    const summaryTotal = document.getElementById('summary-total');
    const summaryStatus = document.getElementById('summary-status');
    const validationMessages = document.getElementById('validation-messages');

    state.scenes = scenePanels.map((panel, index) => {
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

    const attrFeatureInputs = Array.from(document.querySelectorAll('.attr-feature'));
    const attrPolarity = document.getElementById('attr-polarity');
    const attrEvidence = document.getElementById('attr-evidence');
    const attrAbstraction = document.getElementById('attr-abstraction');
    const attrConfidence = document.getElementById('attr-confidence');
    const attrError = document.getElementById('attr-error');
    const attrTruth = document.getElementById('attr-truth');

    function setStatus(message, type = 'info') {
      if (!saveStatus) return;
      saveStatus.textContent = message;
      saveStatus.className = `muted status-${type}`;
    }

    function getActiveScene() {
      return state.scenes[state.activeScene];
    }

    function collectAttributes() {
      const features = attrFeatureInputs
        .filter((input) => input.checked)
        .map((input) => input.value.trim())
        .filter(Boolean);

      const attrs = {
        feature: features.join(' '),
        polarity: attrPolarity?.value || '',
        evidence: attrEvidence?.value || '',
        abstraction: attrAbstraction?.value || '',
        confidence: attrConfidence?.value || '',
        error: attrError?.value || '',
        truth_alignment: attrTruth?.value || '',
      };

      Object.keys(attrs).forEach((key) => {
        if (!attrs[key]) {
          delete attrs[key];
        }
      });
      return attrs;
    }

    function attrsToString(attrs) {
      return Object.entries(attrs)
        .map(([key, value]) => ` ${key}="${value}"`)
        .join('');
    }

    function wrapSelection(tag) {
      const scene = getActiveScene();
      if (!scene) {
        return;
      }
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

      if (selected.includes('<') || selected.includes('>')) {
        setStatus('Selection intersects existing tags; adjust selection.', 'error');
        return;
      }

      const lastOpen = value.lastIndexOf('<', start);
      const lastClose = value.lastIndexOf('>', start);
      if (lastOpen > -1 && lastOpen > lastClose) {
        setStatus('Selection starts inside a tag declaration.', 'error');
        return;
      }

      const attrs = collectAttributes();
      const attrString = attrsToString(attrs);
      const tagText = `<${tag}${attrString}>${selected}</${tag}>`;
      const nextValue = `${value.slice(0, start)}${tagText}${value.slice(end)}`;

      textarea.value = nextValue;
      textarea.selectionStart = textarea.selectionEnd = start + tagText.length;
      scene.body = textarea.value;
      renderPreview();
      renderTagList();
      refreshTagTotals();
      setStatus(`Applied ${tag}.`, 'success');
    }

    function escapeHtml(str) {
      return str
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
    }

    function highlightPlain(text) {
      let escaped = escapeHtml(text);
      if (!state.highlightHedges || hedges.length === 0) {
        return escaped.replace(/\n/g, '<br>');
      }
      hedges.forEach((token) => {
        const pattern = new RegExp(`\\b${escapeRegex(token)}\\b`, 'gi');
        escaped = escaped.replace(pattern, (match) => `<mark class="hedge">${match}</mark>`);
      });
      return escaped.replace(/\n/g, '<br>');
    }

    function escapeRegex(str) {
      return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    }

    function parseAttrString(attrString) {
      const attrs = {};
      if (!attrString) {
        return attrs;
      }
      const attrPattern = /([a-z_]+)="([^"]*)"/g;
      let match;
      while ((match = attrPattern.exec(attrString)) !== null) {
        attrs[match[1]] = match[2];
      }
      return attrs;
    }

    function renderChips(attrs) {
      const chips = [];
      if (attrs.feature) {
        attrs.feature
          .split(/[,\s]+/)
          .filter(Boolean)
          .forEach((token) => {
            chips.push(`<span class="tag-chip">${token}</span>`);
          });
      }
      ['polarity', 'evidence', 'abstraction', 'confidence', 'error', 'truth_alignment'].forEach((key) => {
        if (attrs[key]) {
          chips.push(`<span class="tag-chip">${key}:${attrs[key]}</span>`);
        }
      });
      if (chips.length === 0) {
        return '';
      }
      return `<span class="tag-chips">${chips.join('')}</span>`;
    }

    function renderMarkup(text) {
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
    }

    function renderPreview() {
      const scene = getActiveScene();
      if (!scene || !previewBody) {
        return;
      }
      previewBody.innerHTML = renderMarkup(scene.textarea.value);
    }

    function listTags(text) {
      const pattern = /<([A-Z_]+)([^>]*)>([\s\S]*?)<\/\1>/g;
      const tags = [];
      let match;
      while ((match = pattern.exec(text)) !== null) {
        const snippet = match[3].replace(/\s+/g, ' ').trim().slice(0, 120);
        tags.push({
          tag: match[1],
          attrs: parseAttrString(match[2]),
          snippet,
        });
      }
      return tags;
    }

    function renderTagList() {
      if (!tagList) {
        return;
      }
      const scene = getActiveScene();
      const tags = listTags(scene.textarea.value);
      tagList.innerHTML = tags
        .map((item) => {
          const attrs = Object.entries(item.attrs)
            .map(([key, value]) => `${key}=${value}`)
            .join(', ');
          return `<li><strong>${item.tag}</strong> — ${escapeHtml(item.snippet)}${attrs ? ` <span class="muted">(${escapeHtml(attrs)})</span>` : ''}</li>`;
        })
        .join('');
    }

    function countAllTags() {
      const pattern = /<([A-Z_]+)([^>]*)>/g;
      const counts = {};
      const text = composeDocument();
      let match;
      while ((match = pattern.exec(text)) !== null) {
        const tag = match[1];
        counts[tag] = (counts[tag] || 0) + 1;
      }
      return counts;
    }

    function refreshTagTotals() {
      const counts = countAllTags();
      const total = Object.values(counts).reduce((acc, value) => acc + value, 0);
      if (summaryTotal) {
        summaryTotal.textContent = total;
      }
    }

    function composeDocument() {
      return (
        (state.preamble || '') +
        state.scenes
          .map((scene) => `${scene.heading}${scene.textarea.value}`)
          .join('')
      );
    }

    function clearAttributes() {
      attrFeatureInputs.forEach((input) => {
        input.checked = false;
      });
      if (attrPolarity) attrPolarity.value = '';
      if (attrEvidence) attrEvidence.value = '';
      if (attrAbstraction) attrAbstraction.value = '';
      if (attrConfidence) attrConfidence.value = '';
      if (attrError) attrError.value = '';
      if (attrTruth) attrTruth.value = '';
    }

    function saveDocument() {
      const payload = {
        preamble: state.preamble,
        scenes: state.scenes.map((scene) => ({
          number: scene.number,
          heading: scene.heading,
          body: scene.textarea.value,
        })),
      };

      fetch(`/api/save/${state.participant}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      })
        .then(async (response) => {
          const body = await response.json();
          if (!response.ok) {
            throw body;
          }
          setStatus(body.message || 'Saved.', 'success');
          if (summaryStatus) {
            const timestamp = new Date().toLocaleTimeString();
            summaryStatus.textContent = timestamp;
          }
          refreshTagTotals();
          if (validationMessages) {
            validationMessages.innerHTML = '';
          }
        })
        .catch((err) => {
          const errors = err?.errors || ['Failed to save document.'];
          setStatus(errors[0], 'error');
        });
    }

    function runValidation() {
      fetch('/api/validate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: composeDocument() }),
      })
        .then((response) => response.json())
        .then((body) => {
          if (validationMessages) {
            validationMessages.innerHTML = '';
          }
          const errors = body.errors || [];
          if (errors.length === 0) {
            setStatus('Validation passed — no structural issues detected.', 'success');
          } else {
            setStatus('Validation found issues.', 'error');
            if (validationMessages) {
              validationMessages.innerHTML = errors.map((e) => `<li>${escapeHtml(e)}</li>`).join('');
            }
          }
        })
        .catch(() => {
          setStatus('Validation failed.', 'error');
        });
    }

    function insertEpisodeBlock(data) {
      const scene = getActiveScene();
      if (!scene) return;
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
    }

    function insertTextAtCursor(textarea, text) {
      const start = textarea.selectionStart;
      const end = textarea.selectionEnd;
      const value = textarea.value;
      textarea.value = `${value.slice(0, start)}${text}${value.slice(end)}`;
      const cursor = start + text.length;
      textarea.selectionStart = textarea.selectionEnd = cursor;
    }

    // Scene switching
    sceneTabs.forEach((tab) => {
      tab.addEventListener('click', (event) => {
        const index = Number(event.currentTarget.dataset.sceneIndex);
        if (Number.isNaN(index)) return;
        state.activeScene = index;
        sceneTabs.forEach((t) => t.classList.remove('is-active'));
        scenePanels.forEach((panel) => panel.classList.remove('is-active'));
        tab.classList.add('is-active');
        const panel = scenePanels[index];
        panel.classList.add('is-active');
        const textarea = state.scenes[index].textarea;
        textarea.focus();
        renderPreview();
        renderTagList();
      });
    });

    // Wire textareas
    state.scenes.forEach((scene) => {
      scene.textarea.addEventListener('input', () => {
        scene.body = scene.textarea.value;
        if (state.scenes[state.activeScene] === scene) {
          renderPreview();
          renderTagList();
        }
        refreshTagTotals();
      });
    });

    // Operation buttons
    document.querySelectorAll('.op-btn').forEach((button) => {
      button.addEventListener('click', () => {
        const tag = button.dataset.op;
        if (tag) {
          wrapSelection(tag);
        }
      });
    });

    const saveButton = document.getElementById('btn-save');
    if (saveButton) {
      saveButton.addEventListener('click', () => saveDocument());
    }

    const validateButton = document.getElementById('btn-validate');
    if (validateButton) {
      validateButton.addEventListener('click', () => runValidation());
    }

    const highlightButton = document.getElementById('btn-highlight-hedges');
    if (highlightButton) {
      highlightButton.addEventListener('click', () => {
        state.highlightHedges = !state.highlightHedges;
        highlightButton.textContent = state.highlightHedges ? 'Clear hedge highlight' : 'Highlight hedges';
        renderPreview();
      });
    }

    const clearAttrsButton = document.getElementById('btn-clear-attrs');
    if (clearAttrsButton) {
      clearAttrsButton.addEventListener('click', () => {
        clearAttributes();
        setStatus('Attribute selections cleared.', 'info');
      });
    }

    // Keyboard shortcuts
    window.addEventListener('keydown', (event) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 's') {
        event.preventDefault();
        saveDocument();
      }

      if (!event.ctrlKey && !event.metaKey) {
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

    // Episode dialog
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
        episodeDialog.showModal();
      });

      episodeDialog.addEventListener('close', () => {
        if (episodeDialog.returnValue !== 'confirm') {
          return;
        }
        const formData = new FormData(episodeForm);
        const data = Object.fromEntries(formData.entries());
        insertEpisodeBlock(data);
      });
    }

    // Initial render
    renderPreview();
    renderTagList();
    refreshTagTotals();
  });
})();
