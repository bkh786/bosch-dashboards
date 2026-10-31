/**
 * Bosch Dashboards — AI Copilot Assistant (ai-assistant.js)
 * High-performance, data-aware copilot interface.
 * Features:
 * - Expandable drawer window (normal 440px -> expanded 860px)
 * - Rich formatted table rendering & structured markdown
 * - Live screen filter context awareness & refresh sync
 * - Zero-lag pre-loaded in-memory intelligence
 */

(function () {
  'use strict';

  // State
  const state = {
    isOpen: false,
    isExpanded: false,
    isLoading: false,
    isConnected: true,
    dashboardType: 'program', // 'program' or 'qc'
    history: []
  };

  // SVGs for dynamic icons
  const ICONS = {
    expand: `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="15 3 21 3 21 9"></polyline><polyline points="9 21 3 21 3 15"></polyline><line x1="21" y1="3" x2="14" y2="10"></line><line x1="3" y1="21" x2="10" y2="14"></line></svg>`,
    collapse: `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="4 14 10 14 10 20"></polyline><polyline points="20 10 14 10 14 4"></polyline><line x1="14" y1="10" x2="21" y2="3"></line><line x1="3" y1="21" x2="10" y2="14"></line></svg>`
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
      const reg = document.getElementById('fBranch')?.value || document.getElementById('qcFilterRegion')?.value;
      const aom = document.getElementById('fAOM')?.value || document.getElementById('qcFilterAom')?.value;
      const vm = document.getElementById('fEmp')?.value || document.getElementById('qcFilterVm')?.value;
      const cat = document.getElementById('fCat')?.value;
      const cls = document.getElementById('fClass')?.value;
      const dFrom = document.getElementById('fDateFrom')?.value;
      const dTo = document.getElementById('fDateTo')?.value;
      if (reg && reg !== 'ALL') filters['Region'] = reg;
      if (aom && aom !== 'ALL') filters['AOM'] = aom;
      if (vm && vm !== 'ALL') filters['VM'] = vm;
      if (cat && cat !== 'ALL') filters['Category'] = cat;
      if (cls && cls !== 'ALL') filters['Class'] = cls;
      if (dFrom) filters['From'] = dFrom;
      if (dTo) filters['To'] = dTo;
    } else {
      const mo = document.getElementById('filterMonth')?.value;
      const reg = document.getElementById('filterRegion')?.value;
      const st = document.getElementById('filterState')?.value;
      const aom = document.getElementById('filterAOM')?.value || document.getElementById('filterAom')?.value;
      const vm = document.getElementById('filterVM')?.value || document.getElementById('filterVm')?.value;
      if (mo && mo !== 'ALL') filters['Month'] = mo;
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
      return state.dashboardType === 'qc' ? 'National / All Stores & Audits' : 'National / All VMs & AOMs';
    }
    return keys.map(k => `${k}: ${filters[k]}`).join(' • ');
  }

  // Enhanced Lightweight Markdown to HTML Formatter
  function parseMarkdown(md) {
    if (!md) return '';
    let html = md;

    // Escape basic html tags to prevent XSS
    html = html.replace(/</g, '&lt;').replace(/>/g, '&gt;');

    // Fenced Code blocks ```code```
    html = html.replace(/```([a-z]*)\n([\s\S]*?)```/gm, '<pre class="bosch-ai-code-block"><code>$2</code></pre>');

    // Inline code `code`
    html = html.replace(/`([^`]+)`/g, '<code class="bosch-ai-inline-code">$1</code>');

    // Strip standalone horizontal rules (--- or ***)
    html = html.replace(/^\s*[-*_]{3,}\s*$/gm, '');

    // Headings (# to ######, stripping any duplicate # prefixes)
    html = html.replace(/^\s*#{3,6}\s+(?:#+\s*)?(.*)$/gm, '<h4 class="bosch-ai-h4">$1</h4>');
    html = html.replace(/^\s*#{1,2}\s+(?:#+\s*)?(.*)$/gm, '<h3 class="bosch-ai-h3">$1</h3>');

    // Bold **text**
    html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');

    // Tables (Wrapped in scrollable table wrapper with high-density styling)
    const tableRegex = /((?:\|[^\n]+\|\r?\n?)+)/g;
    html = html.replace(tableRegex, function (match) {
      const rows = match.trim().split('\n');
      if (rows.length < 2) return match;
      
      let tableHtml = '<div class="bosch-ai-table-wrap"><table>';

      rows.forEach((row, idx) => {
        if (row.includes('---')) return; // separator
        const cells = row.split('|').filter((_, i, arr) => i > 0 && i < arr.length - 1);
        if (idx === 0) {
          tableHtml += '<thead><tr>' + cells.map(c => `<th>${c.trim()}</th>`).join('') + '</tr></thead><tbody>';
        } else {
          tableHtml += '<tr>' + cells.map(c => `<td>${c.trim()}</td>`).join('') + '</tr>';
        }
      });
      tableHtml += '</tbody></table></div>';
      return tableHtml;
    });

    // Numbered lists (1. 2. 3.)
    html = html.replace(/^\s*\d+\.\s+(.*)$/gm, '<oli>$1</oli>');
    html = html.replace(/(<oli>.*<\/oli>(\n|(?=<oli>)))/g, '<ol>$1</ol>');
    html = html.replace(/<\/ol>\n?<ol>/g, '');
    html = html.replace(/<\/?oli>/g, match => match === '<oli>' ? '<li>' : '</li>');

    // Unordered lists (- or *) — parsed BEFORE single-asterisk italic
    html = html.replace(/^\s*[-*]\s+(.*)$/gm, '<uli>$1</uli>');
    html = html.replace(/(<uli>.*<\/uli>(\n|(?=<uli>)))/g, '<ul>$1</ul>');
    html = html.replace(/<\/ul>\n?<ul>/g, '');
    html = html.replace(/<\/?uli>/g, match => match === '<uli>' ? '<li>' : '</li>');

    // Single-line Italic *text* (only after bullet lists are converted)
    html = html.replace(/\*([^*\n]+)\*/g, '<em>$1</em>');

    // Paragraphs
    const lines = html.split('\n\n');
    html = lines.map(block => {
      block = block.trim();
      if (!block) return '';
      if (block.startsWith('<div class="bosch-ai-table-wrap"') || 
          block.startsWith('<table') || 
          block.startsWith('<ul') || 
          block.startsWith('<ol') || 
          block.startsWith('<pre') || 
          block.startsWith('<h3') || 
          block.startsWith('<h4')) {
        return block;
      }
      return `<p>${block.replace(/\n/g, '<br>')}</p>`;
    }).join('');

    return html;
  }

  function escapeHtml(str) {
    return (str || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  // Update Live Connection Status Indicator (Green for Connected, Red for Error)
  function updateConnectionStatus(isConnected, tooltip) {
    state.isConnected = isConnected;
    const pill = document.getElementById('boschAiStatusPill');
    const pulseDot = document.getElementById('boschAiPulseDot');

    if (pill) {
      pill.className = `bosch-ai-status-pill ${isConnected ? 'connected' : 'error'}`;
      pill.innerHTML = `
        <span class="bosch-ai-status-dot"></span>
        ${isConnected ? 'Connected &amp; Live' : 'Not Connected / Error'}
      `;
      pill.title = tooltip || (isConnected ? 'AI Assistant connected & dataset ready' : 'AI Assistant not connected');
    }

    if (pulseDot) {
      pulseDot.className = `bosch-ai-pulse-dot ${isConnected ? '' : 'error'}`;
      pulseDot.title = isConnected ? 'Live & Connected' : 'Not Connected';
    }
  }

  // Health check to verify /api/chat connectivity on load
  async function checkHealth() {
    try {
      const res = await fetch('/api/chat', { method: 'GET' });
      if (res.ok) {
        const data = await res.json().catch(() => ({}));
        if (data.apiKeyConfigured !== false) {
          updateConnectionStatus(true);
        } else {
          updateConnectionStatus(false, 'API key missing on server');
        }
      } else {
        updateConnectionStatus(false, `Server status ${res.status}`);
      }
    } catch (e) {
      updateConnectionStatus(false, 'Unable to reach /api/chat endpoint');
    }
  }

  // Generate Welcome Card HTML
  function getWelcomeCardHtml() {
    const isQc = state.dashboardType === 'qc';
    const datasetName = isQc ? 'QC Tracker Audit & Compliance' : 'Visual Merchandising (Oct\'26)';
    const bullet3 = isQc 
      ? 'Ask about VM QC scores, store mistakes, audit pass rates, and compliance.' 
      : 'Ask about VM rankings, AOM coverage %, Cat A/B visits, or 11:30 AM adherence.';

    const suggestions = isQc ? [
      'Top 5 & Bottom 5 VM QC Scores',
      'Most Common Mistakes Reported',
      'AOM-wise Audit Pass Rates',
      'Ref & WM Section Compliance',
      '360 Inside Snap Adherence'
    ] : [
      'Top 5 VM Leaderboard Summary',
      'Which States saw highest Coverage?',
      'Bottom 5 Performers Needing Attention',
      'Cat A vs Cat B Progress',
      'AOM Coverage Breakdown'
    ];

    return `
      <div class="bosch-ai-welcome-card" id="boschAiWelcomeCard">
        <div class="bosch-ai-welcome-title">👋 Welcome to Bosch AI Copilot!</div>
        <div class="bosch-ai-welcome-sub">
          I have the entire <strong>${datasetName}</strong> dataset pre-loaded in working memory.
        </div>
        <ul class="bosch-ai-welcome-features">
          <li><strong>Zero Lag:</strong> Instant analysis without external database queries.</li>
          <li><strong>Screen-Aware:</strong> Your active filters above are automatically synchronized.</li>
          <li><strong>Granular Accuracy:</strong> ${bullet3}</li>
        </ul>
        <div class="bosch-ai-welcome-chips" id="boschAiSuggestions">
          ${suggestions.map(s => `<button class="bosch-ai-chip">${s}</button>`).join('')}
        </div>
      </div>
    `;
  }

  // Build and Inject Assistant DOM
  function injectWidget() {
    state.dashboardType = detectDashboardType();

    // Launcher Button (Matches Screenshot: AI Copilot pill with sparkle icon & green dot)
    const launcher = document.createElement('div');
    launcher.id = 'boschAiLauncher';
    launcher.className = 'bosch-ai-launcher';
    launcher.innerHTML = `
      <div class="bosch-ai-launcher-icon">
        <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
          <line x1="12" y1="2" x2="12" y2="6"></line>
          <line x1="12" y1="18" x2="12" y2="22"></line>
          <line x1="4.93" y1="4.93" x2="7.76" y2="7.76"></line>
          <line x1="16.24" y1="16.24" x2="19.07" y2="19.07"></line>
          <line x1="2" y1="12" x2="6" y2="12"></line>
          <line x1="18" y1="12" x2="22" y2="12"></line>
          <line x1="4.93" y1="19.07" x2="7.76" y2="16.24"></line>
          <line x1="16.24" y1="7.76" x2="19.07" y2="4.93"></line>
        </svg>
      </div>
      <span class="bosch-ai-launcher-title">AI Copilot</span>
      <div class="bosch-ai-pulse-dot" id="boschAiPulseDot" title="Live &amp; Connected"></div>
    `;

    // Drawer Container
    const drawer = document.createElement('div');
    drawer.id = 'boschAiDrawer';
    drawer.className = 'bosch-ai-drawer';

    // Context label
    const initialFilters = getActiveFilters();
    const contextLabel = getFilterSummaryText(initialFilters);

    drawer.innerHTML = `
      <!-- Header -->
      <div class="bosch-ai-header">
        <div class="bosch-ai-header-left">
          <div class="bosch-ai-avatar">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <rect x="2" y="3" width="20" height="14" rx="2"></rect>
              <line x1="8" y1="21" x2="16" y2="21"></line>
              <line x1="12" y1="17" x2="12" y2="21"></line>
            </svg>
          </div>
          <div class="bosch-ai-header-info">
            <div class="bosch-ai-header-title">Bosch AI Copilot</div>
            <div class="bosch-ai-header-subtitle">In-Memory Analytical Intelligence</div>
          </div>
        </div>

        <button type="button" class="bosch-ai-status-pill connected" id="boschAiStatusPill" title="Click to refresh status">
          <span class="bosch-ai-status-dot"></span>Connected &amp; Live
        </button>

        <div class="bosch-ai-header-actions">
          <button class="bosch-ai-btn-icon" id="boschAiBtnClear" title="Clear Conversation">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="3 6 5 6 21 6"></polyline>
              <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
            </svg>
          </button>
          <button class="bosch-ai-btn-icon" id="boschAiBtnExpand" title="Expand window">
            ${ICONS.expand}
          </button>
          <button class="bosch-ai-btn-icon" id="boschAiBtnClose" title="Close">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
        </div>
      </div>

      <!-- Active View Filter Bar (Screen State Awareness) -->
      <div class="bosch-ai-active-bar">
        <div class="bosch-ai-active-tag">🎯 ACTIVE VIEW</div>
        <div class="bosch-ai-active-text" id="boschAiActiveText">${contextLabel}</div>
        <button class="bosch-ai-active-refresh" id="boschAiBtnRefreshView" title="Sync with active screen filters">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2">
            <path d="M23 4v6h-6"></path>
            <path d="M1 20v-6h6"></path>
            <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"></path>
          </svg>
        </button>
      </div>

      <!-- Messages Stream -->
      <div class="bosch-ai-messages" id="boschAiMessages">
        ${getWelcomeCardHtml()}
      </div>

      <!-- Input Footer -->
      <div class="bosch-ai-footer">
        <form class="bosch-ai-input-form" id="boschAiForm">
          <div class="bosch-ai-input-box">
            <textarea id="boschAiTextarea" class="bosch-ai-textarea" rows="1" 
                      placeholder="Ask anything about VM rankings, coverage, or QC..."></textarea>
            <button type="submit" id="boschAiSendBtn" class="bosch-ai-send-btn" title="Send (Enter)">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                <line x1="22" y1="2" x2="11" y2="13"></line>
                <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
              </svg>
            </button>
          </div>
        </form>
        <div class="bosch-ai-footer-note">
          Bosch Program Analytics · In-Memory AI Intelligence · Shift+Enter for newline
        </div>
      </div>
    `;

    document.body.appendChild(launcher);
    document.body.appendChild(drawer);

    bindEvents();
    bindFilterListeners();
    checkHealth();
  }

  // Bind UI Events
  function bindEvents() {
    const launcher = document.getElementById('boschAiLauncher');
    const drawer = document.getElementById('boschAiDrawer');
    const btnClose = document.getElementById('boschAiBtnClose');
    const btnClear = document.getElementById('boschAiBtnClear');
    const btnExpand = document.getElementById('boschAiBtnExpand');
    const btnRefreshView = document.getElementById('boschAiBtnRefreshView');
    const statusPill = document.getElementById('boschAiStatusPill');
    const form = document.getElementById('boschAiForm');
    const textarea = document.getElementById('boschAiTextarea');
    const messagesContainer = document.getElementById('boschAiMessages');

    // Toggle drawer open / close
    launcher.addEventListener('click', () => {
      state.isOpen = !state.isOpen;
      drawer.classList.toggle('open', state.isOpen);
      if (state.isOpen) {
        updateActiveView();
        setTimeout(() => textarea.focus(), 150);
      }
    });

    btnClose.addEventListener('click', () => {
      state.isOpen = false;
      drawer.classList.remove('open');
    });

    // Expand / Collapse Drawer Window
    if (btnExpand) {
      btnExpand.addEventListener('click', () => {
        state.isExpanded = !state.isExpanded;
        drawer.classList.toggle('expanded', state.isExpanded);
        btnExpand.innerHTML = state.isExpanded ? ICONS.collapse : ICONS.expand;
        btnExpand.title = state.isExpanded ? 'Collapse window' : 'Expand window';
      });
    }

    // Refresh Active View on Demand
    if (btnRefreshView) {
      btnRefreshView.addEventListener('click', () => {
        btnRefreshView.style.transform = 'rotate(360deg)';
        updateActiveView();
        setTimeout(() => {
          btnRefreshView.style.transform = 'none';
        }, 300);
      });
    }

    // Status pill re-check
    if (statusPill) {
      statusPill.addEventListener('click', () => {
        statusPill.style.opacity = '0.6';
        checkHealth().finally(() => {
          statusPill.style.opacity = '1';
        });
      });
    }

    // Clear Chat
    btnClear.addEventListener('click', () => {
      state.history = [];
      messagesContainer.innerHTML = getWelcomeCardHtml();
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

    // Delegate Quick suggestion chips click
    messagesContainer.addEventListener('click', (e) => {
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

  // Monitor DOM dropdown filter changes (including dynamically populated filters)
  function bindFilterListeners() {
    const filterIds = state.dashboardType === 'qc' 
      ? ['fBranch', 'fAOM', 'fEmp', 'fCat', 'fClass', 'fDateFrom', 'fDateTo', 'qcFilterRegion', 'qcFilterState', 'qcFilterAom', 'qcFilterVm']
      : ['filterMonth', 'filterRegion', 'filterState', 'filterAOM', 'filterVM', 'filterAom', 'filterVm'];

    filterIds.forEach(id => {
      const el = document.getElementById(id);
      if (el) {
        el.addEventListener('change', () => {
          updateActiveView();
        });
      }
    });

    document.addEventListener('change', (e) => {
      if (e.target && filterIds.includes(e.target.id)) {
        updateActiveView();
      }
    });
  }

  function updateActiveView() {
    const textEl = document.getElementById('boschAiActiveText');
    if (!textEl) return;
    const filters = getActiveFilters();
    textEl.textContent = getFilterSummaryText(filters);
  }

  // Append a message to the UI
  function appendMessage(role, text) {
    const container = document.getElementById('boschAiMessages');
    const msgEl = document.createElement('div');
    msgEl.className = `bosch-ai-msg ${role}`;

    const avatar = role === 'assistant' 
      ? `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M12 2L13.8 8.2L20 10L13.8 11.8L12 18L10.2 11.8L4 10L10.2 8.2L12 2Z"/></svg>`
      : '👤';
    const parsedText = role === 'assistant' ? parseMarkdown(text) : `<p>${escapeHtml(text)}</p>`;

    msgEl.innerHTML = `
      <div class="bosch-ai-msg-avatar">${avatar}</div>
      <div class="bosch-ai-msg-bubble">${parsedText}</div>
    `;

    container.appendChild(msgEl);
    container.scrollTop = container.scrollHeight;
  }

  // Show typing indicator
  function showTyping() {
    const container = document.getElementById('boschAiMessages');
    const typingEl = document.createElement('div');
    typingEl.id = 'boschAiTyping';
    typingEl.className = 'bosch-ai-msg assistant';
    typingEl.innerHTML = `
      <div class="bosch-ai-msg-avatar">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M12 2L13.8 8.2L20 10L13.8 11.8L12 18L10.2 11.8L4 10L10.2 8.2L12 2Z"/></svg>
      </div>
      <div class="bosch-ai-msg-bubble" style="padding: 10px 16px;">
        <div class="bosch-ai-typing">
          <div class="bosch-ai-dot"></div>
          <div class="bosch-ai-dot"></div>
          <div class="bosch-ai-dot"></div>
          <span style="font-size:11px;color:#94a3b8;margin-left:6px;">Consulting pre-loaded dataset...</span>
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
      history: state.history.slice(-4)
    };

    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      removeTyping();

      if (res.status === 401) {
        updateConnectionStatus(false, 'API key missing on server');
        appendMessage('assistant', 
          '⚠️ **Server Configuration Notice**\n\n' +
          'The AI Copilot requires `GEMINI_API_KEY` configured in the server environment variables (e.g., in Vercel project settings or `.env`).'
        );
        return;
      }

      if (!res.ok) {
        updateConnectionStatus(false, `Error (${res.status})`);
        const errData = await res.json().catch(() => ({}));
        const errMessage = errData.error || `Server responded with status ${res.status}`;
        appendMessage('assistant', `⚠️ **Error:** ${errMessage}`);
        return;
      }

      const data = await res.json();
      const reply = data.reply || 'No answer received.';
      updateConnectionStatus(true);
      appendMessage('assistant', reply);
      state.history.push({ role: 'model', text: reply });

    } catch (err) {
      removeTyping();
      updateConnectionStatus(false, 'Connection error');
      console.error('Chat Assistant Fetch Error:', err);
      appendMessage('assistant', 
        `⚠️ **Connection Error:** Could not reach \`/api/chat\` endpoint.`
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
