/**
 * ANTIGRAVITY MULTI-AGENT STUDIO - CORE APPLICATION LOGIC
 * Connects directly to the FastAPI LangGraph backend.
 */

// Application State
const state = {
  apiBaseUrl: localStorage.getItem('antigravity_api_url') || 'http://127.0.0.1:8000',
  theme: localStorage.getItem('antigravity_theme') || 'light',
  currentThreadId: null,
  threads: JSON.parse(localStorage.getItem('antigravity_threads') || '[]'),
  isProcessing: false,
  pendingAction: null,
  lastResponseData: null,
};

// DOM Elements
const elements = {
  chatScroller: document.getElementById('chat-scroller'),
  welcomeHero: document.getElementById('welcome-hero'),
  messagesContainer: document.getElementById('messages-container'),
  chatForm: document.getElementById('chat-form'),
  chatInput: document.getElementById('chat-input'),
  btnSend: document.getElementById('btn-send'),
  btnNewChat: document.getElementById('btn-new-chat'),
  threadList: document.getElementById('thread-list'),
  currentThreadDisplay: document.getElementById('current-thread-display'),
  workflowStatusBadge: document.getElementById('workflow-status-badge'),
  backendStatusText: document.getElementById('backend-status-text'),
  connectionStatus: document.getElementById('connection-status'),
  btnConfigToggle: document.getElementById('btn-config-toggle'),
  settingsModal: document.getElementById('settings-modal'),
  btnCloseSettings: document.getElementById('btn-close-settings'),
  btnSaveSettings: document.getElementById('btn-save-settings'),
  apiBaseUrlInput: document.getElementById('api-base-url'),
  modalHealthStatus: document.getElementById('modal-health-status'),
  btnClearHistory: document.getElementById('btn-clear-history'),

  // Theme Elements
  btnThemeToggle: document.getElementById('btn-theme-toggle'),
  themeIcon: document.getElementById('theme-icon'),
  themeLabel: document.getElementById('theme-label'),
  hljsThemeLink: document.getElementById('hljs-theme'),
  
  // Knowledge Base
  kbDocCount: document.getElementById('kb-doc-count'),
  kbChunkCount: document.getElementById('kb-chunk-count'),
  docUploadInput: document.getElementById('doc-upload-input'),
  uploadStatus: document.getElementById('upload-status'),
  btnRefreshDocs: document.getElementById('btn-refresh-docs'),

  // Human in the Loop Banner
  confirmationBanner: document.getElementById('confirmation-banner'),
  confTitle: document.getElementById('conf-title'),
  confDescription: document.getElementById('conf-description'),
  confActionData: document.getElementById('conf-action-data'),
  btnConfApprove: document.getElementById('btn-conf-approve'),
  btnConfReject: document.getElementById('btn-conf-reject'),

  // Inspector Drawer
  btnShowInspector: document.getElementById('btn-show-inspector'),
  btnCloseInspector: document.getElementById('btn-close-inspector'),
  inspectorDrawer: document.getElementById('inspector-drawer'),
  drawerTabs: document.querySelectorAll('.drawer-tab'),
  tabPanes: document.querySelectorAll('.tab-pane'),

  // Quick Prompt Cards
  quickCards: document.querySelectorAll('.quick-card'),
  agentChips: document.querySelectorAll('.agent-chip'),
};

// ==========================================================================
// INITIALIZATION
// ==========================================================================

document.addEventListener('DOMContentLoaded', () => {
  applyTheme(state.theme);
  initializeMarkdown();
  initializeThread();
  renderThreadList();
  checkBackendHealth();
  fetchKnowledgeBaseStats();
  setupEventListeners();

  // Periodic health check every 20 seconds
  setInterval(checkBackendHealth, 20000);
});

function applyTheme(theme) {
  state.theme = theme;
  localStorage.setItem('antigravity_theme', theme);
  document.documentElement.setAttribute('data-theme', theme);
  if (elements.themeIcon && elements.themeLabel) {
    if (theme === 'dark') {
      elements.themeIcon.textContent = '🌙';
      elements.themeLabel.textContent = 'Dark';
      if (elements.hljsThemeLink) {
        elements.hljsThemeLink.href = 'https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/atom-one-dark.min.css';
      }
    } else {
      elements.themeIcon.textContent = '☀️';
      elements.themeLabel.textContent = 'Light';
      if (elements.hljsThemeLink) {
        elements.hljsThemeLink.href = 'https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/github.min.css';
      }
    }
  }
}

function initializeMarkdown() {
  if (window.marked) {
    marked.setOptions({
      highlight: function(code, lang) {
        if (window.hljs && hljs.getLanguage(lang)) {
          return hljs.highlight(code, { language: lang }).value;
        }
        return window.hljs ? hljs.highlightAuto(code).value : code;
      },
      breaks: true,
      gfm: true,
    });
  }
}

function setupEventListeners() {
  // Chat form submit
  elements.chatForm.addEventListener('submit', (e) => {
    e.preventDefault();
    const query = elements.chatInput.value.trim();
    if (!query || state.isProcessing) return;
    executeWorkflow(query);
  });

  // Auto-resize chat textarea
  elements.chatInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      elements.chatForm.dispatchEvent(new Event('submit'));
    }
  });

  elements.chatInput.addEventListener('input', () => {
    elements.chatInput.style.height = 'auto';
    elements.chatInput.style.height = Math.min(elements.chatInput.scrollHeight, 150) + 'px';
  });

  // New Chat
  elements.btnNewChat.addEventListener('click', () => {
    createNewThread();
  });

  // Theme Toggle
  if (elements.btnThemeToggle) {
    elements.btnThemeToggle.addEventListener('click', () => {
      const nextTheme = state.theme === 'light' ? 'dark' : 'light';
      applyTheme(nextTheme);
    });
  }

  // Clear History
  elements.btnClearHistory.addEventListener('click', () => {
    if (confirm('Clear all conversation thread records?')) {
      state.threads = [];
      localStorage.removeItem('antigravity_threads');
      createNewThread();
    }
  });

  // Quick Cards
  elements.quickCards.forEach((card) => {
    card.addEventListener('click', () => {
      const prompt = card.getAttribute('data-prompt');
      if (prompt && !state.isProcessing) {
        elements.chatInput.value = prompt;
        elements.chatForm.dispatchEvent(new Event('submit'));
      }
    });
  });

  // Settings Modal
  elements.btnConfigToggle.addEventListener('click', () => {
    elements.apiBaseUrlInput.value = state.apiBaseUrl;
    elements.settingsModal.classList.remove('hidden');
    testModalHealth();
  });
  elements.btnCloseSettings.addEventListener('click', () => {
    elements.settingsModal.classList.add('hidden');
  });
  elements.btnSaveSettings.addEventListener('click', () => {
    const newUrl = elements.apiBaseUrlInput.value.trim().replace(/\/+$/, '');
    if (newUrl) {
      state.apiBaseUrl = newUrl;
      localStorage.setItem('antigravity_api_url', newUrl);
      elements.settingsModal.classList.add('hidden');
      checkBackendHealth();
      fetchKnowledgeBaseStats();
    }
  });

  // Human-in-the-Loop Confirmation
  elements.btnConfApprove.addEventListener('click', () => {
    if (state.pendingAction && !state.isProcessing) {
      elements.confirmationBanner.classList.add('hidden');
      executeWorkflow('proceed', { confirmAction: true });
    }
  });

  elements.btnConfReject.addEventListener('click', () => {
    if (state.pendingAction && !state.isProcessing) {
      elements.confirmationBanner.classList.add('hidden');
      executeWorkflow('cancel', { confirmAction: false });
    }
  });

  // Inspector Drawer Toggle
  elements.btnShowInspector.addEventListener('click', () => {
    elements.inspectorDrawer.classList.toggle('closed');
  });
  elements.btnCloseInspector.addEventListener('click', () => {
    elements.inspectorDrawer.classList.add('closed');
  });

  // Inspector Tabs
  elements.drawerTabs.forEach((tab) => {
    tab.addEventListener('click', () => {
      elements.drawerTabs.forEach((t) => t.classList.remove('active'));
      elements.tabPanes.forEach((p) => p.classList.remove('active'));

      tab.classList.add('active');
      const targetPane = document.getElementById(tab.getAttribute('data-tab'));
      if (targetPane) targetPane.classList.add('active');
    });
  });

  // Document Upload
  elements.docUploadInput.addEventListener('change', handleDocumentUpload);
  elements.btnRefreshDocs.addEventListener('click', fetchKnowledgeBaseStats);
}

// ==========================================================================
// THREAD & SESSION MANAGEMENT
// ==========================================================================

function generateThreadId() {
  return 'thread_' + Math.random().toString(16).substring(2, 10);
}

function initializeThread() {
  if (state.threads.length > 0) {
    switchThread(state.threads[0].id);
  } else {
    createNewThread();
  }
}

function createNewThread() {
  const newId = generateThreadId();
  state.currentThreadId = newId;
  const newThread = {
    id: newId,
    title: 'New Conversation',
    createdAt: new Date().toISOString(),
    messages: [],
  };
  state.threads.unshift(newThread);
  saveThreads();
  renderThreadList();
  switchThread(newId);
}

function switchThread(threadId) {
  state.currentThreadId = threadId;
  elements.currentThreadDisplay.textContent = threadId;
  elements.confirmationBanner.classList.add('hidden');
  state.pendingAction = null;

  const currentThread = state.threads.find((t) => t.id === threadId);
  renderThreadList();

  // Clear chat view
  elements.messagesContainer.innerHTML = '';
  if (!currentThread || currentThread.messages.length === 0) {
    elements.welcomeHero.style.display = 'flex';
  } else {
    elements.welcomeHero.style.display = 'none';
    currentThread.messages.forEach((msg) => {
      renderMessage(msg.role, msg.content, msg.extraData);
    });
    scrollToBottom();
  }

  resetInspector();
}

function saveThreads() {
  localStorage.setItem('antigravity_threads', JSON.stringify(state.threads.slice(0, 30)));
}

function renderThreadList() {
  elements.threadList.innerHTML = '';
  state.threads.forEach((thread) => {
    const item = document.createElement('div');
    item.className = `thread-item ${thread.id === state.currentThreadId ? 'active' : ''}`;
    item.innerHTML = `
      <span class="thread-title" title="${escapeHtml(thread.title)}">${escapeHtml(thread.title)}</span>
      <span style="font-size:0.65rem; color:var(--text-muted);">${formatTime(thread.createdAt)}</span>
    `;
    item.addEventListener('click', () => switchThread(thread.id));
    elements.threadList.appendChild(item);
  });
}

function updateThreadTitle(threadId, newTitle) {
  const thread = state.threads.find((t) => t.id === threadId);
  if (thread && thread.title === 'New Conversation') {
    thread.title = newTitle.slice(0, 32) + (newTitle.length > 32 ? '...' : '');
    saveThreads();
    renderThreadList();
  }
}

// ==========================================================================
// WORKFLOW EXECUTION & CHAT
// ==========================================================================

async function executeWorkflow(userMessage, options = {}) {
  const { confirmAction = null } = options;
  state.isProcessing = true;
  setUIRunning(true);

  // Hide welcome hero on first message
  elements.welcomeHero.style.display = 'none';

  // Add user message to UI
  if (confirmAction === null) {
    appendMessageToState('user', userMessage);
    renderMessage('user', userMessage);
    updateThreadTitle(state.currentThreadId, userMessage);
  } else {
    const actionLabel = confirmAction ? 'Confirmed action: Proceed' : 'Rejected action: Cancelled';
    appendMessageToState('user', actionLabel);
    renderMessage('user', actionLabel);
  }

  elements.chatInput.value = '';
  elements.chatInput.style.height = 'auto';
  scrollToBottom();

  // Create temporary loading assistant bubble
  const loadingBubble = createLoadingBubble();
  elements.messagesContainer.appendChild(loadingBubble);
  scrollToBottom();

  try {
    const payload = {
      message: userMessage,
      thread_id: state.currentThreadId,
    };
    if (confirmAction !== null) {
      payload.confirm_action = confirmAction;
    }

    const response = await fetch(`${state.apiBaseUrl}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || `Server responded with ${response.status}`);
    }

    const data = await response.json();
    state.lastResponseData = data;

    // Remove loading bubble
    loadingBubble.remove();

    // Render Assistant Response
    appendMessageToState('assistant', data.response || 'Task completed.', data);
    renderMessage('assistant', data.response || 'Task completed.', data);

    // Update Inspector Drawer
    updateInspector(data);

    // Handle Human-in-the-loop pending action
    if (data.confirmation_required && data.pending_action) {
      showConfirmationBanner(data.pending_action);
    } else {
      elements.confirmationBanner.classList.add('hidden');
      state.pendingAction = null;
    }

    // Highlight active agents in roster
    highlightExecutedAgents(data.agent_history || []);

  } catch (err) {
    loadingBubble.remove();
    const errorText = `**Workflow Error**: ${err.message}`;
    appendMessageToState('assistant', errorText);
    renderMessage('assistant', errorText);
    console.error('Workflow error:', err);
  } finally {
    state.isProcessing = false;
    setUIRunning(false);
    scrollToBottom();
  }
}

function appendMessageToState(role, content, extraData = null) {
  const currentThread = state.threads.find((t) => t.id === state.currentThreadId);
  if (currentThread) {
    currentThread.messages.push({ role, content, extraData, timestamp: new Date().toISOString() });
    saveThreads();
  }
}

// ==========================================================================
// MESSAGE RENDERING
// ==========================================================================

function renderMessage(role, content, extraData = null) {
  const row = document.createElement('div');
  row.className = `message-row ${role}`;

  const avatar = document.createElement('div');
  avatar.className = 'message-avatar';
  avatar.textContent = role === 'user' ? '👤' : '🤖';

  const body = document.createElement('div');
  body.className = 'message-body';

  const contentDiv = document.createElement('div');
  contentDiv.className = 'message-content';

  if (role === 'assistant' && extraData) {
    // Pipeline Steps Indicator
    if (extraData.agent_history && extraData.agent_history.length > 0) {
      const pipelineBar = document.createElement('div');
      pipelineBar.className = 'agent-pipeline-bar';

      const stepsContainer = document.createElement('div');
      stepsContainer.className = 'pipeline-steps';

      extraData.agent_history.forEach((step, idx) => {
        if (idx > 0) {
          const arrow = document.createElement('span');
          arrow.className = 'pipeline-arrow';
          arrow.textContent = '→';
          stepsContainer.appendChild(arrow);
        }
        const chip = document.createElement('span');
        chip.className = `pipeline-step ${step.status === 'completed' ? 'completed' : ''}`;
        chip.innerHTML = `${getAgentIcon(step.agent)} ${capitalize(step.agent)}`;
        stepsContainer.appendChild(chip);
      });

      pipelineBar.appendChild(stepsContainer);

      const statusTag = document.createElement('span');
      statusTag.className = `badge ${extraData.status === 'completed' ? 'badge-success' : 'badge-warning'}`;
      statusTag.textContent = extraData.status || 'Finished';
      pipelineBar.appendChild(statusTag);

      contentDiv.appendChild(pipelineBar);
    }
  }

  // Render markdown text
  const textDiv = document.createElement('div');
  textDiv.className = 'markdown-body';
  textDiv.innerHTML = window.marked ? marked.parse(content) : escapeHtml(content).replace(/\n/g, '<br>');
  contentDiv.appendChild(textDiv);

  // Render Specialized Results Accordions if present
  if (role === 'assistant' && extraData) {
    const specialContainer = createSpecializedOutputsContainer(extraData);
    if (specialContainer) {
      contentDiv.appendChild(specialContainer);
    }
  }

  body.appendChild(contentDiv);
  row.appendChild(avatar);
  row.appendChild(body);

  elements.messagesContainer.appendChild(row);
}

function createSpecializedOutputsContainer(data) {
  const container = document.createElement('div');
  container.className = 'specialized-outputs';
  let hasItems = false;

  // 1. Code Results
  if (data.code_results && data.code_results.code) {
    hasItems = true;
    const accordion = createAccordionItem('💻 Coding Agent Output & Sandbox', () => {
      const box = document.createElement('div');
      box.className = 'code-box';
      box.innerHTML = `
        <div class="code-box-header">
          <span>Python Execution (${data.code_results.execution_status || 'verified'})</span>
          <span>Return code: ${data.code_results.return_value ?? 0}</span>
        </div>
        <pre><code class="language-python">${escapeHtml(data.code_results.code)}</code></pre>
        ${data.code_results.stdout ? `<div style="padding:8px 12px; background:rgba(0,0,0,0.4); border-top:1px solid var(--border-color);"><strong style="color:var(--accent-cyan); font-size:0.75rem;">Standard Output:</strong><pre style="margin-top:4px; font-size:0.75rem; color:#a7f3d0;">${escapeHtml(data.code_results.stdout)}</pre></div>` : ''}
      `;
      return box;
    });
    container.appendChild(accordion);
  }

  // 2. Database Results
  if (data.database_results && (data.database_results.rows || data.database_results.tables)) {
    hasItems = true;
    const accordion = createAccordionItem('🗄️ Database Agent Results', () => {
      const box = document.createElement('div');
      if (data.database_results.rows && data.database_results.rows.length > 0) {
        const table = document.createElement('table');
        table.className = 'db-table';
        const headers = Object.keys(data.database_results.rows[0]);
        let thead = `<tr>${headers.map((h) => `<th>${escapeHtml(h)}</th>`).join('')}</tr>`;
        let tbody = data.database_results.rows.map((row) => `<tr>${headers.map((h) => `<td>${escapeHtml(String(row[h]))}</td>`).join('')}</tr>`).join('');
        table.innerHTML = `<thead>${thead}</thead><tbody>${tbody}</tbody>`;
        box.appendChild(table);
      } else if (data.database_results.tables) {
        box.innerHTML = `<p style="color:var(--accent-cyan); font-weight:600;">Available Tables: ${data.database_results.tables.join(', ')}</p>`;
      }
      return box;
    });
    container.appendChild(accordion);
  }

  // 3. Validation Audit
  if (data.validation_result) {
    hasItems = true;
    const vr = data.validation_result;
    const isPass = (vr.status || '').toUpperCase() === 'PASS';
    const accordion = createAccordionItem(`🛡️ QA Audit: ${isPass ? 'PASSED' : 'NEEDS REVISION'}`, () => {
      const box = document.createElement('div');
      box.innerHTML = `
        <div style="margin-bottom:8px; display:flex; align-items:center; gap:8px;">
          <span class="badge ${isPass ? 'badge-success' : 'badge-warning'}">${escapeHtml(vr.status || 'PASS')}</span>
          <span style="font-size:0.75rem; color:var(--text-muted);">${vr.issues?.length || 0} issues detected</span>
        </div>
        ${vr.feedback ? `<p style="font-size:0.8rem; color:var(--text-secondary); margin-bottom:6px;"><strong>Feedback:</strong> ${escapeHtml(vr.feedback)}</p>` : ''}
        ${vr.issues && vr.issues.length > 0 ? `<ul style="font-size:0.75rem; color:var(--accent-amber); padding-left:16px;">${vr.issues.map((i) => `<li>${escapeHtml(i)}</li>`).join('')}</ul>` : ''}
      `;
      return box;
    });
    container.appendChild(accordion);
  }

  return hasItems ? container : null;
}

function createAccordionItem(title, contentBuilder) {
  const wrapper = document.createElement('div');
  wrapper.className = 'output-accordion';

  const header = document.createElement('div');
  header.className = 'accordion-header';
  header.innerHTML = `<span>${title}</span><span>▾</span>`;

  const body = document.createElement('div');
  body.className = 'accordion-body';
  body.appendChild(contentBuilder());

  header.addEventListener('click', () => {
    const isVisible = body.style.display !== 'none';
    body.style.display = isVisible ? 'none' : 'block';
    header.querySelector('span:last-child').textContent = isVisible ? '▸' : '▾';
  });

  wrapper.appendChild(header);
  wrapper.appendChild(body);
  return wrapper;
}

function createLoadingBubble() {
  const row = document.createElement('div');
  row.className = 'message-row assistant';
  row.innerHTML = `
    <div class="message-avatar">🤖</div>
    <div class="message-body">
      <div class="message-content" style="display:flex; align-items:center; gap:10px;">
        <span class="pulse-indicator online" style="width:10px; height:10px;"></span>
        <span style="color:var(--text-secondary); font-size:0.88rem;">
          Multi-Agent System planning & coordinating specialists...
        </span>
      </div>
    </div>
  `;
  return row;
}

// ==========================================================================
// HUMAN IN THE LOOP CONFIRMATION
// ==========================================================================

function showConfirmationBanner(action) {
  state.pendingAction = action;
  elements.confTitle.textContent = `Action Requires Human Confirmation: ${capitalize(action.action || 'External Action')}`;
  elements.confDescription.textContent = action.reason || 'This action has external side effects and requires explicit user authorization before execution.';

  elements.confActionData.innerHTML = `
    <div><strong>Action:</strong> ${escapeHtml(action.action || 'unknown')}</div>
    <div><strong>Parameters:</strong> ${escapeHtml(JSON.stringify(action.params || {}))}</div>
  `;

  elements.confirmationBanner.classList.remove('hidden');
  scrollToBottom();
}

// ==========================================================================
// RIGHT DRAWER INSPECTOR
// ==========================================================================

function updateInspector(data) {
  // Plan Tab
  const planContainer = document.getElementById('tab-plan');
  if (data.plan && data.plan.length > 0) {
    planContainer.innerHTML = `
      <div style="font-size:0.8rem; font-weight:600; margin-bottom:8px; color:var(--accent-cyan);">Execution Plan:</div>
      <ol style="padding-left:18px; display:flex; flex-direction:column; gap:6px; font-size:0.8rem;">
        ${data.plan.map((step) => `<li>${escapeHtml(step)}</li>`).join('')}
      </ol>
    `;
  }

  // Code Tab
  const codeContainer = document.getElementById('tab-code');
  if (data.code_results) {
    codeContainer.innerHTML = `
      <div style="font-size:0.8rem; font-weight:600; margin-bottom:8px; color:var(--accent-cyan);">Generated Code:</div>
      <pre style="background:#0f172a; padding:10px; border-radius:6px; font-size:0.75rem; overflow-x:auto;"><code>${escapeHtml(data.code_results.code || 'None')}</code></pre>
      ${data.code_results.stdout ? `<div style="margin-top:8px;"><strong>Output:</strong><pre style="font-size:0.75rem; color:#a7f3d0;">${escapeHtml(data.code_results.stdout)}</pre></div>` : ''}
    `;
  }

  // DB Tab
  const dbContainer = document.getElementById('tab-db');
  if (data.database_results) {
    dbContainer.innerHTML = `<pre style="font-size:0.75rem; color:var(--text-secondary);">${escapeHtml(JSON.stringify(data.database_results, null, 2))}</pre>`;
  }

  // Audit Tab
  const auditContainer = document.getElementById('tab-audit');
  if (data.validation_result) {
    auditContainer.innerHTML = `<pre style="font-size:0.75rem; color:var(--text-secondary);">${escapeHtml(JSON.stringify(data.validation_result, null, 2))}</pre>`;
  }

  // Logs Tab
  const logsContainer = document.getElementById('tab-logs');
  if (data.agent_logs && data.agent_logs.length > 0) {
    logsContainer.innerHTML = data.agent_logs.map((log) => `
      <div style="border-bottom:1px solid var(--border-color); padding:8px 0;">
        <span style="color:var(--accent-primary); font-weight:600; font-size:0.75rem;">${capitalize(log.agent || 'Agent')}:</span>
        <span style="font-size:0.75rem; color:var(--text-secondary); margin-left:4px;">${escapeHtml(log.action || '')}</span>
      </div>
    `).join('');
  }
}

function resetInspector() {
  document.getElementById('tab-plan').innerHTML = '<div class="inspector-empty">No active execution plan. Send a prompt to begin.</div>';
  document.getElementById('tab-code').innerHTML = '<div class="inspector-empty">No code execution results available.</div>';
  document.getElementById('tab-db').innerHTML = '<div class="inspector-empty">No database query results available.</div>';
  document.getElementById('tab-audit').innerHTML = '<div class="inspector-empty">No validator audit results available.</div>';
  document.getElementById('tab-logs').innerHTML = '<div class="inspector-empty">No agent execution logs.</div>';
}

// ==========================================================================
// RAG KNOWLEDGE BASE
// ==========================================================================

async function fetchKnowledgeBaseStats() {
  try {
    const res = await fetch(`${state.apiBaseUrl}/documents`);
    if (res.ok) {
      const data = await res.json();
      elements.kbDocCount.textContent = data.total_documents || 0;
      elements.kbChunkCount.textContent = data.total_chunks || 0;
    }
  } catch (err) {
    console.warn('Could not fetch knowledge base stats:', err);
  }
}

async function handleDocumentUpload(e) {
  const file = e.target.files[0];
  if (!file) return;

  const formData = new FormData();
  formData.append('file', file);

  elements.uploadStatus.textContent = `Uploading ${file.name}...`;
  elements.uploadStatus.style.color = 'var(--accent-cyan)';

  try {
    const res = await fetch(`${state.apiBaseUrl}/documents/upload`, {
      method: 'POST',
      body: formData,
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Upload failed');
    }

    const data = await res.json();
    elements.uploadStatus.textContent = `Indexed ${data.chunks_created} chunks!`;
    elements.uploadStatus.style.color = 'var(--accent-emerald)';
    fetchKnowledgeBaseStats();
  } catch (err) {
    elements.uploadStatus.textContent = `Error: ${err.message}`;
    elements.uploadStatus.style.color = 'var(--accent-rose)';
  } finally {
    elements.docUploadInput.value = '';
    setTimeout(() => {
      elements.uploadStatus.textContent = '';
    }, 4000);
  }
}

// ==========================================================================
// HEALTH & UTILITIES
// ==========================================================================

async function checkBackendHealth() {
  try {
    const res = await fetch(`${state.apiBaseUrl}/health`, { method: 'GET' });
    if (res.ok) {
      const indicator = elements.connectionStatus.querySelector('.pulse-indicator');
      indicator.className = 'pulse-indicator online';
      elements.backendStatusText.textContent = 'Backend Online';
      return true;
    }
  } catch (_) {
    // Offline
  }
  const indicator = elements.connectionStatus.querySelector('.pulse-indicator');
  indicator.className = 'pulse-indicator offline';
  elements.backendStatusText.textContent = 'Backend Offline';
  return false;
}

async function testModalHealth() {
  elements.modalHealthStatus.className = 'badge badge-neutral';
  elements.modalHealthStatus.textContent = 'Checking...';
  const url = elements.apiBaseUrlInput.value.trim().replace(/\/+$/, '');
  try {
    const res = await fetch(`${url}/health`);
    if (res.ok) {
      elements.modalHealthStatus.className = 'badge badge-success';
      elements.modalHealthStatus.textContent = 'Connected (200 OK)';
      return;
    }
  } catch (_) {}
  elements.modalHealthStatus.className = 'badge badge-warning';
  elements.modalHealthStatus.textContent = 'Unreachable';
}

function setUIRunning(running) {
  elements.workflowStatusBadge.className = running ? 'badge badge-running' : 'badge badge-neutral';
  elements.workflowStatusBadge.textContent = running ? 'Processing...' : 'Ready';
  elements.btnSend.disabled = running;
  elements.chatInput.disabled = running;
}

function highlightExecutedAgents(history) {
  elements.agentChips.forEach((chip) => chip.classList.remove('active'));
  history.forEach((step) => {
    const chip = document.querySelector(`.agent-chip[data-agent="${step.agent}"]`);
    if (chip) chip.classList.add('active');
  });
}

function getAgentIcon(agent) {
  const icons = {
    supervisor: '👑',
    research: '🔍',
    analysis: '📊',
    coder: '💻',
    database: '🗄️',
    document: '📑',
    email: '✉️',
    calendar: '📅',
    writer: '✍️',
    validator: '🛡️',
  };
  return icons[agent] || '🤖';
}

function capitalize(str) {
  if (!str) return '';
  return str.charAt(0).toUpperCase() + str.slice(1);
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function formatTime(iso) {
  try {
    const d = new Date(iso);
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  } catch (_) {
    return '';
  }
}

function scrollToBottom() {
  setTimeout(() => {
    elements.chatScroller.scrollTop = elements.chatScroller.scrollHeight;
  }, 50);
}
