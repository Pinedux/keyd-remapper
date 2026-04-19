const API_BASE = 'http://127.0.0.1:8474';

const state = {
  devices: [],
  configs: [],
  keydStatus: null,
  configContent: '',
  firmwareResults: [],
  monitorConnected: false,
  monitorSocket: null,
  monitorLines: [],
  monitorRetryTimer: null,
  monitorBannerShown: false,
  monitorManualDisconnect: false,
  availableKeys: [],
  currentSection: 'dashboard',
  errors: [],
  loading: {}
};

/* ─── DOM refs ─── */
let app, sidebar, mainContent;

/* ─── Init ─── */
document.addEventListener('DOMContentLoaded', () => {
  app = document.getElementById('app');
  renderLayout();
  router();
  window.addEventListener('hashchange', router);
  checkBackend();
});

/* ─── Layout ─── */
function renderLayout() {
  app.innerHTML = `
    <button class="menu-toggle" id="menuToggle" aria-label="Toggle menu">☰</button>
    <div class="sidebar-overlay" id="sidebarOverlay"></div>
    <aside class="sidebar" id="sidebar">
      <div class="sidebar-header">
        <div class="sidebar-logo">⌨</div>
        <div class="sidebar-title">Keyd Remapper</div>
      </div>
      <nav class="sidebar-nav">
        <a class="nav-item" href="#dashboard" data-section="dashboard">
          <span class="nav-icon">◈</span> Dashboard
        </a>
        <a class="nav-item" href="#keyboards" data-section="keyboards">
          <span class="nav-icon">🖮</span> Keyboards
        </a>
        <a class="nav-item" href="#remap" data-section="remap">
          <span class="nav-icon">⇄</span> Remap
        </a>
        <a class="nav-item" href="#firmware" data-section="firmware">
          <span class="nav-icon">🔧</span> Firmware
        </a>
        <a class="nav-item" href="#monitor" data-section="monitor">
          <span class="nav-icon">◉</span> Monitor
        </a>
      </nav>
      <div class="sidebar-footer">
        keyd remapper v1.0
      </div>
    </aside>
    <main class="main-content" id="mainContent">
      <div id="banners"></div>
      <div id="dashboard" class="section"></div>
      <div id="keyboards" class="section"></div>
      <div id="remap" class="section"></div>
      <div id="firmware" class="section"></div>
      <div id="monitor" class="section"></div>
    </main>
  `;

  sidebar = document.getElementById('sidebar');
  mainContent = document.getElementById('mainContent');

  document.getElementById('menuToggle').addEventListener('click', toggleSidebar);
  document.getElementById('sidebarOverlay').addEventListener('click', closeSidebar);

  // nav click closes mobile sidebar
  document.querySelectorAll('.nav-item').forEach(el => {
    el.addEventListener('click', () => closeSidebar());
  });
}

function toggleSidebar() {
  sidebar.classList.toggle('open');
  document.getElementById('sidebarOverlay').classList.toggle('active');
}
function closeSidebar() {
  sidebar.classList.remove('open');
  document.getElementById('sidebarOverlay').classList.remove('active');
}

/* ─── Router ─── */
function router() {
  const rawHash = window.location.hash.replace('#', '') || 'dashboard';
  const [section] = rawHash.split('?');
  state.currentSection = section;

  document.querySelectorAll('.nav-item').forEach(el => {
    el.classList.toggle('active', el.dataset.section === section);
  });

  document.querySelectorAll('.section').forEach(el => {
    el.classList.toggle('active', el.id === section);
  });

  switch (section) {
    case 'dashboard': renderDashboard(); break;
    case 'keyboards': renderKeyboards(); break;
    case 'remap': renderRemap(); break;
    case 'firmware': renderFirmware(); break;
    case 'monitor': renderMonitor(); break;
    default: renderDashboard();
  }
}

function getHashParams() {
  const rawHash = window.location.hash.replace('#', '');
  const idx = rawHash.indexOf('?');
  if (idx === -1) return {};
  const params = new URLSearchParams(rawHash.slice(idx + 1));
  const obj = {};
  for (const [k, v] of params) obj[k] = v;
  return obj;
}

/* ─── API helpers ─── */
async function apiFetch(path, options = {}) {
  const url = `${API_BASE}${path}`;
  try {
    const res = await fetch(url, { ...options, headers: { 'Content-Type': 'application/json', ...options.headers } });
    if (!res.ok) {
      if (res.status === 404) return null;
      let msg = `HTTP ${res.status}`;
      try { const err = await res.json(); msg = err.detail || err.message || msg; } catch (_) {}
      throw new Error(msg);
    }
    return await res.json().catch(() => ({}));
  } catch (err) {
    if (!options._silent) showBanner(err.message, 'error');
    throw err;
  }
}

async function apiFetchNoBanner(path, options = {}) {
  try {
    return await apiFetch(path, { ...options, _silent: true });
  } catch {
    return null;
  }
}

async function checkBackend() {
  try {
    await fetch(`${API_BASE}/api/keyd/status`, { method: 'GET', signal: AbortSignal.timeout(3000) });
    clearBanners();
  } catch {
    showBanner('Backend unreachable. Is the app running?', 'error');
  }
}

/* ─── Banners ─── */
function showBanner(msg, type = 'error') {
  const container = document.getElementById('banners');
  const id = 'banner-' + Math.random().toString(36).slice(2);
  const div = document.createElement('div');
  div.className = `banner banner-${type}`;
  div.id = id;
  div.innerHTML = `<span>${type === 'error' ? '⚠' : '✓'}</span> <span>${escapeHtml(msg)}</span>`;
  container.appendChild(div);
  setTimeout(() => div.remove(), 6000);
}

function clearBanners() {
  const container = document.getElementById('banners');
  if (container) container.innerHTML = '';
}

function escapeHtml(str) {
  return String(str).replace(/[&<>"']/g, m => ({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;','\'':'&#39;' }[m]));
}

/* ─── Dashboard ─── */
function renderDashboard() {
  const el = document.getElementById('dashboard');
  const status = state.keydStatus;
  const installed = status?.installed;
  const active = status?.active;
  const version = status?.version || '—';
  const keyboards = state.devices.filter(d => d.device_type === 'keyboard');
  const others = state.devices.filter(d => d.device_type !== 'keyboard');

  el.innerHTML = `
    <div class="page-header">
      <h1>Dashboard</h1>
      <p>Overview of your keyd remapping environment.</p>
    </div>

    <div class="grid grid-2 mb-2">
      <div class="card">
        <div class="card-header">
          <div>
            <div class="card-title">keyd Status</div>
            <div class="card-subtitle">System service state</div>
          </div>
          ${status ? `
            <span class="status-badge ${active ? 'status-success' : installed ? 'status-warning' : 'status-error'}">
              <span class="status-dot"></span>
              ${active ? 'Active' : installed ? 'Inactive' : 'Not Installed'}
            </span>
          ` : '<span class="spinner"></span>'}
        </div>
        <div class="keyboard-meta mb-2">
          <div class="keyboard-meta-label">Version</div>
          <div class="keyboard-meta-item">${escapeHtml(version)}</div>
        </div>
        <div class="btn-group">
          <button class="btn btn-secondary btn-sm" id="dashCheckStatus">Check Status</button>
          ${!installed ? `<button class="btn btn-primary btn-sm" id="dashInstall">Install keyd</button>` : ''}
          ${installed && !active ? `<button class="btn btn-success btn-sm" id="dashActivate">Activate keyd</button>` : ''}
        </div>
      </div>

      <div class="card">
        <div class="card-header">
          <div>
            <div class="card-title">Devices</div>
            <div class="card-subtitle">Detected input devices</div>
          </div>
          <span class="status-badge status-info">
            <span class="status-dot"></span>
            ${keyboards.length} keyboards, ${others.length} other devices
          </span>
        </div>
        <p class="text-muted text-sm mb-2">Manage device remapping and view device details.</p>
        <a class="btn btn-primary btn-sm" href="#keyboards">View Devices →</a>
      </div>
    </div>

    <h2 class="mb-1" style="font-size:1.1rem;font-weight:600;">Quick Links</h2>
    <div class="grid">
      <a class="quick-link" href="#remap">
        <div class="quick-link-icon">⇄</div>
        <div>
          <div class="quick-link-text">Remap Keys</div>
          <div class="quick-link-desc">Edit keyd configuration and apply changes</div>
        </div>
      </a>
      <a class="quick-link" href="#firmware">
        <div class="quick-link-icon">🔧</div>
        <div>
          <div class="quick-link-text">Find Firmware</div>
          <div class="quick-link-desc">Search QMK/VIAL firmware for your keyboard</div>
        </div>
      </a>
      <a class="quick-link" href="#monitor">
        <div class="quick-link-icon">◉</div>
        <div>
          <div class="quick-link-text">Live Monitor</div>
          <div class="quick-link-desc">Watch keyd events in real time</div>
        </div>
      </a>
    </div>
  `;

  el.querySelector('#dashCheckStatus')?.addEventListener('click', () => {
    loadKeydStatus().then(() => renderDashboard());
  });
  el.querySelector('#dashInstall')?.addEventListener('click', async () => {
    try {
      await apiFetch('/api/keyd/install', { method: 'POST' });
      showBanner('keyd installed successfully', 'success');
      await loadKeydStatus();
      renderDashboard();
    } catch { /* banner shown by helper */ }
  });
  el.querySelector('#dashActivate')?.addEventListener('click', async () => {
    try {
      await apiFetch('/api/keyd/activate', { method: 'POST' });
      showBanner('keyd activated successfully', 'success');
      await loadKeydStatus();
      renderDashboard();
    } catch { /* banner shown by helper */ }
  });

  if (!status) loadKeydStatus().then(() => renderDashboard());
}

async function loadKeydStatus() {
  try {
    state.keydStatus = await apiFetch('/api/keyd/status');
  } catch {
    state.keydStatus = { installed: false, active: false, version: 'unknown' };
  }
}

/* ─── Keyboards / Devices ─── */
async function renderKeyboards() {
  const el = document.getElementById('keyboards');
  const keyboards = state.devices.filter(d => d.device_type === 'keyboard');
  const others = state.devices.filter(d => d.device_type !== 'keyboard');

  const renderList = (list) => list.map(d => deviceCard(d)).join('');

  el.innerHTML = `
    <div class="page-header flex items-center justify-between">
      <div>
        <h1>Devices</h1>
        <p>Detected input devices on your system.</p>
      </div>
      <button class="btn btn-secondary btn-sm" id="kbRefresh">↻ Refresh</button>
    </div>
    <div class="grid" id="kbGrid">
      ${state.devices.length === 0
        ? '<div class="empty-state"><div class="empty-state-icon">🖮</div><p>No devices detected yet.</p></div>'
        : renderList(keyboards) + renderList(others)}
    </div>
  `;

  el.querySelector('#kbRefresh')?.addEventListener('click', async () => {
    await loadDevices();
    renderKeyboards();
  });

  el.querySelectorAll('.device-configure-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      location.hash = `#remap?device=${encodeURIComponent(btn.dataset.deviceId)}`;
    });
  });

  if (state.devices.length === 0) {
    await loadDevices();
    renderKeyboards();
  }
}

function deviceCard(dev) {
  const type = dev.device_type || 'other';
  const isKeyboard = type === 'keyboard';
  const badgeClass = type === 'keyboard' ? 'keyboard' : type === 'mouse' ? 'mouse' : 'other';
  const badgeText = type === 'keyboard' ? 'Keyboard' : type === 'mouse' ? 'Mouse' : 'Other device';
  const managed = dev.is_keyd_managed;
  const deviceId = escapeHtml(dev.device_id || dev.id || '');

  return `
    <div class="card device-card ${type} ${managed ? '' : 'card-hover'}">
      ${managed ? '<div class="managed-badge">Managed</div>' : ''}
      <div class="device-type-badge ${badgeClass}">${badgeText}</div>
      <div class="card-title">${escapeHtml(dev.name || 'Unknown Device')}</div>
      <div class="card-subtitle">${escapeHtml(dev.device_path || '')}</div>
      <div class="keyboard-meta">
        <div class="keyboard-meta-label">Vendor ID</div>
        <div class="keyboard-meta-item">${escapeHtml(dev.vendor_id || '—')}</div>
        <div class="keyboard-meta-label">Product ID</div>
        <div class="keyboard-meta-item">${escapeHtml(dev.product_id || '—')}</div>
      </div>
      ${isKeyboard ? `<button class="btn btn-primary btn-sm mt-2 device-configure-btn" data-device-id="${deviceId}">Configure</button>` : ''}
    </div>
  `;
}

async function loadDevices() {
  try {
    state.devices = await apiFetch('/api/keyboards') || [];
  } catch {
    state.devices = [];
  }
}

/* ─── Remap ─── */
async function renderRemap() {
  const el = document.getElementById('remap');
  const params = getHashParams();
  const preselectedDevice = params.device;

  // Ensure data is loaded
  if (state.configs.length === 0) await loadConfigs();
  if (state.devices.length === 0) await loadDevices();

  const keyboards = state.devices.filter(d => d.device_type === 'keyboard');

  const selectorOptions = [
    `<option value="default">Default (all devices)</option>`,
    ...keyboards.map(kb => `<option value="device:${escapeHtml(kb.device_id || kb.id || '')}">New config for ${escapeHtml(kb.name || 'Unknown Device')}</option>`),
    ...state.configs.map(cfg => `<option value="config:${escapeHtml(cfg)}">${escapeHtml(cfg)}</option>`)
  ].join('');

  el.innerHTML = `
    <div class="page-header">
      <h1>Remap</h1>
      <p>Edit your keyd configuration and add key mappings.</p>
    </div>

    <div class="card mb-2">
      <div class="card-title mb-1">Configuration</div>
      <select id="configSelector" class="config-selector">
        ${selectorOptions}
      </select>
      <div class="card-title mb-1">Quick Mapping</div>
      <div class="form-row">
        <div class="form-group">
          <label class="form-label">From key</label>
          <select id="fromKey"><option value="">Loading…</option></select>
        </div>
        <div class="form-group">
          <label class="form-label">To key</label>
          <select id="toKey"><option value="">Loading…</option></select>
        </div>
        <button class="btn btn-primary" id="addMapping">+ Add</button>
      </div>
    </div>

    <div class="card">
      <div class="card-header">
        <div class="card-title">keyd Config</div>
        <div class="btn-group">
          <button class="btn btn-secondary btn-sm" id="loadConfig">Load Config</button>
          <button class="btn btn-primary btn-sm" id="saveConfig">Save & Apply</button>
        </div>
      </div>
      <textarea id="configText" rows="16" placeholder="[ids]\n\n*\n\n[main]\n# your mappings here\n"></textarea>
      <div id="configMsg" class="mt-1 text-sm"></div>
    </div>
  `;

  const textarea = el.querySelector('#configText');
  const selector = el.querySelector('#configSelector');
  const msgEl = el.querySelector('#configMsg');

  // Handle preselected device from URL
  if (preselectedDevice) {
    const deviceOption = Array.from(selector.options).find(opt => opt.value === `device:${preselectedDevice}`);
    if (deviceOption) {
      selector.value = deviceOption.value;
      textarea.value = `[ids]\n${preselectedDevice}\n\n[main]\n`;
    }
  }

  selector.addEventListener('change', async () => {
    msgEl.innerHTML = '';
    const val = selector.value;
    if (val.startsWith('device:')) {
      const id = val.slice(7);
      textarea.value = `[ids]\n${id}\n\n[main]\n`;
      return;
    }
    if (val === 'default') {
      try {
        const data = await apiFetch('/api/keyd/config');
        textarea.value = data?.content || data?.config || '';
      } catch { /* banner shown */ }
      return;
    }
    if (val.startsWith('config:')) {
      const name = val.slice(7);
      try {
        const data = await apiFetch(`/api/keyd/config/${encodeURIComponent(name)}`);
        textarea.value = data?.content || data?.config || '';
      } catch { /* banner shown */ }
      return;
    }
  });

  // Trigger load for default if nothing preselected
  if (!preselectedDevice) {
    try {
      const data = await apiFetch('/api/keyd/config');
      textarea.value = data?.content || data?.config || '';
    } catch { /* banner shown */ }
  }

  el.querySelector('#loadConfig').addEventListener('click', async () => {
    const val = selector.value;
    msgEl.innerHTML = '';
    try {
      let data;
      if (val.startsWith('config:')) {
        const name = val.slice(7);
        data = await apiFetch(`/api/keyd/config/${encodeURIComponent(name)}`);
      } else if (val.startsWith('device:')) {
        showBanner('Create a new device-specific config', 'success');
        return;
      } else {
        data = await apiFetch('/api/keyd/config');
      }
      textarea.value = data?.content || data?.config || '';
      showBanner('Configuration loaded', 'success');
    } catch { /* banner shown */ }
  });

  el.querySelector('#saveConfig').addEventListener('click', async () => {
    const content = textarea.value;
    const val = selector.value;
    msgEl.innerHTML = '';
    try {
      if (val.startsWith('device:')) {
        const deviceId = val.slice(7);
        await apiFetch('/api/keyd/apply-device', {
          method: 'POST',
          body: JSON.stringify({ device_id: deviceId, content })
        });
      } else if (val.startsWith('config:')) {
        const name = val.slice(7);
        await apiFetch(`/api/keyd/config/${encodeURIComponent(name)}`, {
          method: 'POST',
          body: JSON.stringify({ content })
        });
      } else {
        await apiFetch('/api/keyd/config', {
          method: 'POST',
          body: JSON.stringify({ content })
        });
      }
      if (!val.startsWith('device:')) {
        await apiFetch('/api/keyd/reload', { method: 'POST' });
      }
      msgEl.innerHTML = '<span style="color:var(--success)">✓ Saved and applied.</span>';
      showBanner('Config saved and applied', 'success');
    } catch (err) {
      msgEl.innerHTML = `<span style="color:var(--error)">✗ ${escapeHtml(err.message)}</span>`;
    }
  });

  el.querySelector('#addMapping').addEventListener('click', () => {
    const from = el.querySelector('#fromKey').value;
    const to = el.querySelector('#toKey').value;
    if (!from || !to) return;
    const line = `${from} = ${to}\n`;
    textarea.value += line;
    state.configContent = textarea.value;
  });

  // populate key dropdowns
  if (state.availableKeys.length === 0) {
    try {
      const data = await apiFetch('/api/keyd/keys');
      state.availableKeys = Array.isArray(data) ? data : (data.keys || []);
    } catch {
      state.availableKeys = [];
    }
  }
  const opts = state.availableKeys.map(k => `<option value="${escapeHtml(k)}">${escapeHtml(k)}</option>`).join('');
  el.querySelector('#fromKey').innerHTML = '<option value="">Select key…</option>' + opts;
  el.querySelector('#toKey').innerHTML = '<option value="">Select key…</option>' + opts;
}

async function loadConfigs() {
  try {
    const data = await apiFetch('/api/keyd/configs');
    state.configs = Array.isArray(data) ? data : (data.configs || []);
  } catch {
    state.configs = [];
  }
}

/* ─── Firmware ─── */
function renderFirmware() {
  const el = document.getElementById('firmware');
  el.innerHTML = `
    <div class="page-header">
      <h1>Firmware</h1>
      <p>Search for keyboard firmware on QMK, VIAL, and GitHub.</p>
    </div>
    <div class="card mb-2">
      <div class="form-row">
        <div class="form-group" style="flex:1">
          <label class="form-label">Search query</label>
          <input type="text" id="fwQuery" placeholder="e.g. corne, planck, kyria…">
        </div>
        <button class="btn btn-primary" id="fwSearch">Search</button>
      </div>
    </div>
    <div class="grid" id="fwGrid">
      ${state.firmwareResults.length === 0
        ? '<div class="empty-state"><div class="empty-state-icon">🔧</div><p>Enter a query to search for firmware.</p></div>'
        : state.firmwareResults.map(r => firmwareCard(r)).join('')}
    </div>
  `;

  const input = el.querySelector('#fwQuery');
  el.querySelector('#fwSearch').addEventListener('click', () => searchFirmware(input.value));
  input.addEventListener('keydown', e => { if (e.key === 'Enter') searchFirmware(input.value); });
}

function firmwareCard(r) {
  return `
    <div class="card firmware-card card-hover">
      <div class="flex items-center justify-between">
        <h3>${escapeHtml(r.title || r.name || 'Untitled')}</h3>
        <span class="source-badge">${escapeHtml(r.source || 'Unknown')}</span>
      </div>
      <p>${escapeHtml(r.description || r.desc || 'No description available.')}</p>
      ${r.url ? `<a href="${escapeHtml(r.url)}" target="_blank" rel="noopener">${escapeHtml(r.url)}</a>` : ''}
      ${r.html_url ? `<a href="${escapeHtml(r.html_url)}" target="_blank" rel="noopener">${escapeHtml(r.html_url)}</a>` : ''}
    </div>
  `;
}

async function searchFirmware(query) {
  if (!query.trim()) return;
  const grid = document.getElementById('fwGrid');
  grid.innerHTML = '<div class="empty-state"><div class="spinner"></div><p>Searching…</p></div>';
  try {
    const data = await apiFetch(`/api/firmware/search?q=${encodeURIComponent(query.trim())}`);
    state.firmwareResults = Array.isArray(data) ? data : (data.results || []);
    renderFirmware();
  } catch {
    state.firmwareResults = [];
    renderFirmware();
  }
}

/* ─── Monitor ─── */
function renderMonitor() {
  const el = document.getElementById('monitor');
  el.innerHTML = `
    <div class="page-header flex items-center justify-between">
      <div>
        <h1>Monitor</h1>
        <p>Live keyd event stream.</p>
      </div>
      <div class="flex items-center gap-2">
        ${state.monitorRetryTimer ? '<div class="retry-indicator" id="monRetry"><span class="spinner"></span> Reconnecting…</div>' : ''}
        <button class="btn ${state.monitorConnected ? 'btn-danger' : 'btn-primary'}" id="monToggle">
          ${state.monitorConnected ? 'Disconnect' : 'Connect'}
        </button>
      </div>
    </div>
    <div class="terminal" id="monTerminal">
      <div class="terminal-line system">Ready. Press Connect to start monitoring events.</div>
    </div>
  `;

  el.querySelector('#monToggle').addEventListener('click', toggleMonitor);

  // restore existing lines if reconnecting render
  const term = el.querySelector('#monTerminal');
  if (state.monitorLines.length) {
    term.innerHTML = state.monitorLines.join('');
    term.scrollTop = term.scrollHeight;
  }
}

function toggleMonitor() {
  if (state.monitorConnected) {
    state.monitorManualDisconnect = true;
    disconnectMonitor();
  } else {
    state.monitorManualDisconnect = false;
    connectMonitor();
  }
}

function connectMonitor() {
  if (state.monitorSocket) return;
  state.monitorManualDisconnect = false;
  const ws = new WebSocket('ws://127.0.0.1:8474/ws/keyd-monitor');
  state.monitorSocket = ws;

  ws.onopen = () => {
    state.monitorConnected = true;
    state.monitorBannerShown = false;
    clearRetryTimer();
    appendMonitorLine('Connected to keyd monitor.', 'system');
    renderMonitor();
  };

  ws.onmessage = (ev) => {
    try {
      const msg = JSON.parse(ev.data);
      if (msg.type === 'ping') {
        return;
      }
      if (msg.type === 'event') {
        const text = msg.data || '';
        let type = 'system';
        const lower = text.toLowerCase();
        if (lower.includes('down') || lower.includes('press')) type = 'keydown';
        else if (lower.includes('up') || lower.includes('release')) type = 'keyup';
        appendMonitorLine(text, type);
        return;
      }
      appendMonitorLine(JSON.stringify(msg), 'system');
    } catch {
      const data = ev.data;
      let type = 'system';
      const lower = data.toLowerCase();
      if (lower.includes('down') || lower.includes('press')) type = 'keydown';
      else if (lower.includes('up') || lower.includes('release')) type = 'keyup';
      appendMonitorLine(data, type);
    }
  };

  ws.onclose = () => {
    state.monitorConnected = false;
    state.monitorSocket = null;
    appendMonitorLine('Disconnected.', 'system');
    renderMonitor();
    if (!state.monitorManualDisconnect) {
      scheduleMonitorRetry();
    }
  };

  ws.onerror = () => {
    if (!state.monitorBannerShown) {
      showBanner('WebSocket error. Is the backend running?', 'error');
      state.monitorBannerShown = true;
    }
    state.monitorConnected = false;
    state.monitorSocket = null;
    renderMonitor();
  };
}

function disconnectMonitor() {
  clearRetryTimer();
  state.monitorManualDisconnect = true;
  if (state.monitorSocket) {
    state.monitorSocket.close();
  }
}

function scheduleMonitorRetry() {
  if (state.monitorRetryTimer) return;
  state.monitorRetryTimer = setTimeout(() => {
    state.monitorRetryTimer = null;
    if (!state.monitorConnected) {
      connectMonitor();
    }
  }, 3000);
  renderMonitor();
}

function clearRetryTimer() {
  if (state.monitorRetryTimer) {
    clearTimeout(state.monitorRetryTimer);
    state.monitorRetryTimer = null;
    renderMonitor();
  }
}

function appendMonitorLine(text, type) {
  const term = document.getElementById('monTerminal');
  const line = `<div class="terminal-line ${type}">${escapeHtml(text)}</div>`;
  state.monitorLines.push(line);
  if (state.monitorLines.length > 500) state.monitorLines.shift();
  if (term) {
    term.insertAdjacentHTML('beforeend', line);
    term.scrollTop = term.scrollHeight;
  }
}
