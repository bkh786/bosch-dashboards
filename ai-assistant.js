/**
 * Bosch Dashboards — Gemini AI Chat Assistant (ai-assistant.js)
 * High-performance, data-aware copilot interface powered by Gemini 2.0 Flash.
 * Automatically synchronizes with live dashboard state, active cascading filters,
 * and pre-loaded datasets (Program & QC).
 */

(function () {
  'use strict';

  // State
  const state = {
    isOpen: false,
    isSettingsOpen: false,
    isLoading: false,
    dashboardType: 'program', // 'program' or 'qc'
    history: [],
    apiKey: localStorage.getItem('bosch_gemini_api_key') || ''
  };

  // Determine current dashboard context
  function detectDashboardType() {
    const path = window.location.pathname.toLowerCase();
    const title = (document.title || '').toLowerCase();
    if (path.includes('qc') || title.includes('qc') || title.includes('quality')) {
      return 'qc';
    }
    return 'program';
  }

  // Get current active filter selections from the DOM
  function getActiveFilters() {
    const filters = {};
    if (state.dashboardType === 'qc') {
      const reg = document.getElementById('qcFilterRegion')?.value;
      const st = document.getElementById('qcFilterState')?.value;
      const aom = document.getElementById('qcFilterAom')?.value;
      const vm = document.getElementById('qcFilterVm')?.value;
      if (reg && reg !== 'ALL') filters['Region'] = reg;
      if (st && st !== 'ALL') filters['State'] = st;
      if (aom && aom !== 'ALL') filters['AOM'] = aom;
      if (vm && vm !== 'ALL') filters['VM'] = vm;
    } else {
      const reg = document.getElementById('filterRegion')?.value;
      const st = document.getElementById('filterState')?.value;
      const aom = document.getElementById('filterAom')?.value;
      const vm = document.getElementById('filterVm')?.value;
      if (reg && reg !== 'ALL') filters['Region'] = reg;
      if (st && st !== 'ALL') filters['State'] = st;
      if (aom && aom !== 'ALL') filters['AOM'] = aom;
      if (vm && vm !== 'ALL') filters['VM'] = vm;
    }
    return filters;
  }

  // Generate friendly label for context banner
  function getFilterSummaryText(filters) {
    const keys = Object.keys(filters);
    if (keys.length === 0) {
      return state.dashboardType === 'qc' ? 'Full QC Audit Dataset' : 'Full National Program Dataset';
    }
    return keys.map(k => `${k}: ${filters[k]}`).join(' • ');
  }

  // Lightweight Markdown to HTML Formatter
  function parseMarkdown(md) {
    if (!md) return '';
    let html = md;

    // Escape basic html tags to prevent XSS
    html = html.replace(/</g, '&lt;').replace(/>/g, '&gt;');

    // Code blocks ```code```
    html = html.replace(/```([a-z]*)\n([\s\S]*?)```/gm, '<pre><code>$2</code></pre>');

    // Inline code `code`
    html = html.replace(/`([^`]+)`/g, '<code style="background:rgba(255,255,255,0.1);padding:2px 5px;border-radius:4px;font-family:IBM Plex Mono,monospace;font-size:11px;">$1</code>');

    // Bold **text**
    html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');

    // Italic *text*
    html = html.replace(/\*([^*]+)\*/g, '<em>$1</em>');

    // Tables
    const tableRegex = /((?:\|[^\n]+\|\r?\n)+)/g;
    html = html.replace(tableRegex, function (match) {
      const rows = match.trim().split('\n');
      if (rows.length < 2) return match;
      
      let tableHtml = '<table>';
      let isHeader = true;

      rows.forEach((row, idx) => {
        if (row.includes('---')) return; // separator
        const cells = row.split('|').filter((_, i, arr) => i > 0 && i < arr.length - 1);
        if (idx === 0) {
          tableHtml += '<thead><tr>' + cells.map(c => `<th>${c.trim()}</th>`).join('') + '</tr></thead><tbody>';
        } else {
          tableHtml += '<tr>' + cells.map(c => `<td>${c.trim()}</td>`).join('') + '</tr>';
        }
      });
      tableHtml += '</tbody></table>';
      return tableHtml;
    });

    // Unordered lists (- or *)
    html = html.replace(/^\s*[-*]\s+(.*)$/gm, '<li>$1</li>');
    html = html.replace(/(<li>.*<\/li>(\n|(?=<li>)))/g, '<ul>$1</ul>');
    html = html.replace(/<\/ul>\n?<ul>/g, '');

    // Paragraphs
    const lines = html.split('\n\n');
    html = lines.map(block => {
      block = block.trim();
      if (!block) return '';
      if (block.startsWith('<table') || block.startsWith('<ul') || block.startsWith('<pre') || block.startsWith('<h')) {
        return block;
      }
      return `<p>${block.replace(/\n/g, '<br>')}</p>`;
    }).join('');

    return html;
  }

  // Build and Inject Assistant DOM
  function injectWidget() {
    state.dashboardType = detectDashboardType();

    // Launcher Button
    const launcher = document.createElement('div');
    launcher.id = 'boschAiLauncher';
    launcher.className = 'bosch-ai-launcher';
    launcher.innerHTML = `
      <div class="bosch-ai-launcher-icon">
        <svg viewBox="0 0 24 24">
          <path d="M12 2L14.4 9.6L22 12L14.4 14.4L12 22L9.6 14.4L2 12L9.6 9.6L12 2Z"/>
        </svg>
      </div>
      <div class="bosch-ai-launcher-text">
        <span class="bosch-ai-launcher-title">Bosch AI Copilot</span>
        <span class="bosch-ai-launcher-sub">Gemini 2.5 Flash</span>
      </div>
      <div class="bosch-ai-pulse-dot" title="Data pre-loaded"></div>
    `;

    // Drawer Container
    const drawer = document.createElement('div');
    drawer.id = 'boschAiDrawer';
    drawer.className = 'bosch-ai-drawer';

    // Context label
    const initialFilters = getActiveFilters();
    const contextLabel = getFilterSummaryText(initialFilters);

    // Dynamic suggestions based on dashboard
    const suggestions = state.dashboardType === 'qc' ? [
      '🏆 Top 5 & Bottom 5 VM QC Scores',
      '⚠️ Most Common Mistakes Reported',
      '📊 AOM-wise Audit Pass Rates',
      '🔍 Ref & WM Section Compliance',
      '📸 360 Inside Snap Adherence'
    ] : [
      '🏆 Top 5 VM Leaderboard Summary',
      '⚠️ Bottom 5 Performers & Laggards',
      '📊 AOM Coverage Breakdown',
      '⏰ 11:30 AM First Visit Adherence',
      '🎯 Cat A vs Cat B Progress'
    ];

    drawer.innerHTML = `
      <div class="bosch-ai-header">
        <div class="bosch-ai-header-left">
          <div class="bosch-ai-avatar">
            <svg viewBox="0 0 24 24">
              <path d="M12 2L14.4 9.6L22 12L14.4 14.4L12 22L9.6 14.4L2 12L9.6 9.6L12 2Z"/>
            </svg>
          </div>
          <div class="bosch-ai-header-info">
            <div class="bosch-ai-header-title">
              Bosch AI Copilot
              <span class="bosch-ai-badge">Gemini 2.5</span>
            </div>
            <div class="bosch-ai-header-subtitle">
              <span>●</span> Pre-loaded Live Data
            </div>
          </div>
        </div>
        <div class="bosch-ai-header-actions">
          <button class="bosch-ai-btn-icon" id="boschAiBtnSettings" title="API Settings">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="3"></circle>
              <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path>
            </svg>
          </button>
          <button class="bosch-ai-btn-icon" id="boschAiBtnClear" title="Clear Conversation">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="3 6 5 6 21 6"></polyline>
              <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
            </svg>
          </button>
          <button class="bosch-ai-btn-icon" id="boschAiBtnClose" title="Minimize">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
        </div>
      </div>

      <!-- Settings Sub-panel -->
      <div class="bosch-ai-settings-panel" id="boschAiSettingsPanel">
        <div class="bosch-ai-settings-title">
          <span>Gemini API Configuration</span>
          <span style="font-size:10px;color:#94a3b8;">Stored locally in browser</span>
        </div>
        <div class="bosch-ai-input-group">
          <input type="password" id="boschAiApiKeyInput" class="bosch-ai-settings-input" 
                 placeholder="AIzaSy... (leave blank if set on server)" 
                 value="${state.apiKey}">
          <button id="boschAiBtnSaveKey" class="bosch-ai-btn-sm">Save</button>
        </div>
        <div style="font-size:10px;color:#94a3b8;line-height:1.4;">
          Optional: If your key is already defined in <code style="color:#ff6b72;">.env</code> or Vercel Environment Variables, no key is needed here.
        </div>
      </div>

      <!-- Active Context Banner -->
      <div class="bosch-ai-context-banner">
        <span>Active View:</span>
        <span class="bosch-ai-context-tag" id="boschAiContextTag">
          🎯 ${contextLabel}
        </span>
      </div>

      <!-- Messages Stream -->
      <div class="bosch-ai-messages" id="boschAiMessages">
        <div class="bosch-ai-msg assistant">
          <div class="bosch-ai-msg-avatar">⚡</div>
          <div class="bosch-ai-msg-bubble">
            <p><strong>Hello! I'm your Bosch Field Performance Copilot.</strong></p>
            <p>The entire master dataset is pre-loaded into my working memory. You can ask me any question about VM rankings, AOM performance, coverage %, Category A/B visits, or first-visit adherence benchmarks.</p>
            <p style="font-size:11px;color:#94a3b8;margin-top:6px;">Try one of the quick suggestions below or type your question!</p>
          </div>
        </div>
      </div>

      <!-- Quick Suggestion Chips -->
      <div class="bosch-ai-suggestions" id="boschAiSuggestions">
        ${suggestions.map(s => `<button class="bosch-ai-chip">${s}</button>`).join('')}
      </div>

      <!-- Input Footer -->
      <div class="bosch-ai-footer">
        <form class="bosch-ai-input-form" id="boschAiForm">
          <textarea id="boschAiTextarea" class="bosch-ai-textarea" rows="1" 
                    placeholder="Ask anything about Bosch VM or QC performance..."></textarea>
          <button type="submit" id="boschAiSendBtn" class="bosch-ai-send-btn" title="Send (Enter)">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
              <line x1="22" y1="2" x2="11" y2="13"></line>
              <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
            </svg>
          </button>
        </form>
        <div class="bosch-ai-footer-note">
          Google Gemini 2.5 Flash • Pre-loaded in-memory context • Zero lag
        </div>
      </div>
    `;

    document.body.appendChild(launcher);
    document.body.appendChild(drawer);

    bindEvents();
    bindFilterListeners();
  }

  // Bind UI Events
  function bindEvents() {
    const launcher = document.getElementById('boschAiLauncher');
    const drawer = document.getElementById('boschAiDrawer');
    const btnClose = document.getElementById('boschAiBtnClose');
    const btnClear = document.getElementById('boschAiBtnClear');
    const btnSettings = document.getElementById('boschAiBtnSettings');
    const settingsPanel = document.getElementById('boschAiSettingsPanel');
    const btnSaveKey = document.getElementById('boschAiBtnSaveKey');
    const apiKeyInput = document.getElementById('boschAiApiKeyInput');
    const form = document.getElementById('boschAiForm');
    const textarea = document.getElementById('boschAiTextarea');
    const suggestionsContainer = document.getElementById('boschAiSuggestions');

    // Toggle drawer
    launcher.addEventListener('click', () => {
      state.isOpen = !state.isOpen;
      drawer.classList.toggle('open', state.isOpen);
      if (state.isOpen) {
        updateContextTag();
        setTimeout(() => textarea.focus(), 150);
      }
    });

    btnClose.addEventListener('click', () => {
      state.isOpen = false;
      drawer.classList.remove('open');
    });

    // Toggle settings panel
    btnSettings.addEventListener('click', () => {
      state.isSettingsOpen = !state.isSettingsOpen;
      settingsPanel.classList.toggle('active', state.isSettingsOpen);
    });

    // Save API Key
    btnSaveKey.addEventListener('click', () => {
      const val = apiKeyInput.value.trim();
      state.apiKey = val;
      localStorage.setItem('bosch_gemini_api_key', val);
      btnSaveKey.textContent = 'Saved!';
      setTimeout(() => {
        btnSaveKey.textContent = 'Save';
        state.isSettingsOpen = false;
        settingsPanel.classList.remove('active');
      }, 1200);
    });

    // Clear Chat
    btnClear.addEventListener('click', () => {
      state.history = [];
      const messagesContainer = document.getElementById('boschAiMessages');
      messagesContainer.innerHTML = `
        <div class="bosch-ai-msg assistant">
          <div class="bosch-ai-msg-avatar">⚡</div>
          <div class="bosch-ai-msg-bubble">
            <p><strong>Conversation refreshed.</strong></p>
            <p>The pre-loaded dataset is ready. How can I assist you with your field analytics?</p>
          </div>
        </div>
      `;
    });

    // Auto-resize textarea & Enter key to submit
    textarea.addEventListener('input', () => {
      textarea.style.height = 'auto';
      textarea.style.height = Math.min(textarea.scrollHeight, 100) + 'px';
    });

    textarea.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        form.dispatchEvent(new Event('submit'));
      }
    });

    // Quick suggestion chips
    suggestionsContainer.addEventListener('click', (e) => {
      const chip = e.target.closest('.bosch-ai-chip');
      if (chip) {
        const text = chip.textContent.replace(/^[^a-zA-Z0-9]+/, '').trim();
        textarea.value = text;
        form.dispatchEvent(new Event('submit'));
      }
    });

    // Handle Form Submit
    form.addEventListener('submit', (e) => {
      e.preventDefault();
      const query = textarea.value.trim();
      if (!query || state.isLoading) return;

      textarea.value = '';
      textarea.style.height = 'auto';
      handleSendMessage(query);
    });
  }

  // Monitor DOM dropdown filter changes to keep context tag and prompt synced
  function bindFilterListeners() {
    const filterIds = state.dashboardType === 'qc' 
      ? ['qcFilterRegion', 'qcFilterState', 'qcFilterAom', 'qcFilterVm']
      : ['filterRegion', 'filterState', 'filterAom', 'filterVm'];

    filterIds.forEach(id => {
      const el = document.getElementById(id);
      if (el) {
        el.addEventListener('change', () => {
          updateContextTag();
        });
      }
    });
  }

  function updateContextTag() {
    const tag = document.getElementById('boschAiContextTag');
    if (!tag) return;
    const filters = getActiveFilters();
    tag.textContent = `🎯 ${getFilterSummaryText(filters)}`;
  }

  // Append a message to the UI
  function appendMessage(role, text) {
    const container = document.getElementById('boschAiMessages');
    const msgEl = document.createElement('div');
    msgEl.className = `bosch-ai-msg ${role}`;

    const avatar = role === 'assistant' ? '⚡' : '👤';
    const parsedText = role === 'assistant' ? parseMarkdown(text) : `<p>${escapeHtml(text)}</p>`;

    msgEl.innerHTML = `
      <div class="bosch-ai-msg-avatar">${avatar}</div>
      <div class="bosch-ai-msg-bubble">${parsedText}</div>
    `;

    container.appendChild(msgEl);
    container.scrollTop = container.scrollHeight;
  }

  function escapeHtml(str) {
    return (str || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  // Show typing indicator
  function showTyping() {
    const container = document.getElementById('boschAiMessages');
    const typingEl = document.createElement('div');
    typingEl.id = 'boschAiTyping';
    typingEl.className = 'bosch-ai-msg assistant';
    typingEl.innerHTML = `
      <div class="bosch-ai-msg-avatar">⚡</div>
      <div class="bosch-ai-msg-bubble" style="padding: 10px 16px;">
        <div class="bosch-ai-typing">
          <div class="bosch-ai-dot"></div>
          <div class="bosch-ai-dot"></div>
          <div class="bosch-ai-dot"></div>
          <span style="font-size:11px;color:#94a3b8;margin-left:6px;">Consulting pre-loaded data...</span>
        </div>
      </div>
    `;
    container.appendChild(typingEl);
    container.scrollTop = container.scrollHeight;
  }

  function removeTyping() {
    const el = document.getElementById('boschAiTyping');
    if (el) el.remove();
  }

  // Send message to serverless /api/chat
  async function handleSendMessage(query) {
    appendMessage('user', query);
    state.history.push({ role: 'user', text: query });

    state.isLoading = true;
    const sendBtn = document.getElementById('boschAiSendBtn');
    if (sendBtn) sendBtn.disabled = true;
    showTyping();

    const activeFilters = getActiveFilters();

    const payload = {
      prompt: query,
      dashboard: state.dashboardType,
      activeFilters: activeFilters,
      history: state.history.slice(-8),
      apiKey: state.apiKey || undefined
    };

    try {
      const headers = { 'Content-Type': 'application/json' };
      if (state.apiKey) {
        headers['x-gemini-api-key'] = state.apiKey;
      }

      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: headers,
        body: JSON.stringify(payload)
      });

      removeTyping();

      if (res.status === 401) {
        appendMessage('assistant', 
          '⚠️ **Gemini API Key Required**\n\n' +
          'To start querying the pre-loaded dataset, please provide a Gemini API key. ' +
          'You can either add `GEMINI_API_KEY=your_key` into your `.env` file / Vercel Environment Variables, ' +
          'or click the **⚙️ Settings icon** above to paste it for this session.'
        );
        // Automatically open settings panel
        state.isSettingsOpen = true;
        document.getElementById('boschAiSettingsPanel')?.classList.add('active');
        return;
      }

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        const errMessage = errData.error || `Server responded with status ${res.status}`;
        appendMessage('assistant', `⚠️ **Error:** ${errMessage}`);
        return;
      }

      const data = await res.json();
      const reply = data.reply || 'No answer received.';
      appendMessage('assistant', reply);
      state.history.push({ role: 'model', text: reply });

    } catch (err) {
      removeTyping();
      console.error('Chat Assistant Fetch Error:', err);
      appendMessage('assistant', 
        `⚠️ **Network Error:** Could not reach \`/api/chat\` endpoint.\n\n` +
        `If running locally, please start the development server with:\n` +
        `\`\`\`bash\npython3 dev_server.py\n\`\`\`\n` +
        `This enables the \`/api/chat\` Python serverless handler on port 8000.`
      );
    } finally {
      state.isLoading = false;
      if (sendBtn) sendBtn.disabled = false;
    }
  }

  // Initialize once DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', injectWidget);
  } else {
    injectWidget();
  }

})();
