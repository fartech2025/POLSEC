/**
 * POLSEC — Offline Sync Manager
 *
 * Fluxo:
 *  1. Detecta ausência de rede (navigator.onLine + events)
 *  2. Intercepta submit de forms → salva em IndexedDB com status "pending"
 *  3. Ao reconectar → replays as operações em ordem de timestamp
 *  4. Exibe banner e toasts com estado em tempo real
 */

// ── Constantes ────────────────────────────────────────────────────────────────
const POLSEC_DB_NAME    = 'polsec-offline-v1';
const POLSEC_DB_VERSION = 1;
const QUEUE_STORE       = 'sync_queue';

// ── IndexedDB ─────────────────────────────────────────────────────────────────
function openDB() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(POLSEC_DB_NAME, POLSEC_DB_VERSION);
    req.onupgradeneeded = e => {
      const db = e.target.result;
      if (!db.objectStoreNames.contains(QUEUE_STORE)) {
        const store = db.createObjectStore(QUEUE_STORE, { keyPath: 'id', autoIncrement: true });
        store.createIndex('status',    'status');
        store.createIndex('timestamp', 'timestamp');
      }
    };
    req.onsuccess = e => resolve(e.target.result);
    req.onerror   = e => reject(e.target.error);
  });
}

async function enqueue(op) {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(QUEUE_STORE, 'readwrite');
    tx.objectStore(QUEUE_STORE).add(op);
    tx.oncomplete = resolve;
    tx.onerror    = e => reject(e.target.error);
  });
}

async function getPendingOps() {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx  = db.transaction(QUEUE_STORE, 'readonly');
    const req = tx.objectStore(QUEUE_STORE).index('status').getAll('pending');
    req.onsuccess = e => resolve(e.target.result.sort((a, b) => a.timestamp.localeCompare(b.timestamp)));
    req.onerror   = e => reject(e.target.error);
  });
}

async function countPending() {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx  = db.transaction(QUEUE_STORE, 'readonly');
    const req = tx.objectStore(QUEUE_STORE).index('status').count('pending');
    req.onsuccess = e => resolve(e.target.result);
    req.onerror   = e => reject(e.target.error);
  });
}

async function updateOpStatus(id, status, extra = {}) {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx    = db.transaction(QUEUE_STORE, 'readwrite');
    const store = tx.objectStore(QUEUE_STORE);
    const req   = store.get(id);
    req.onsuccess = e => {
      const record = { ...e.target.result, status, ...extra };
      store.put(record);
      tx.oncomplete = resolve;
    };
    req.onerror = e => reject(e.target.error);
  });
}

// ── Banner offline ────────────────────────────────────────────────────────────
let _bannerEl = null;

function getBanner() {
  if (!_bannerEl) {
    _bannerEl = document.createElement('div');
    _bannerEl.id = 'polsec-offline-banner';
    Object.assign(_bannerEl.style, {
      position: 'fixed', top: '0', left: '0', right: '0', zIndex: '9999',
      padding: '9px 20px', fontSize: '13px', fontWeight: '600',
      display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '10px',
      transform: 'translateY(-100%)', transition: 'transform 0.3s ease',
      boxShadow: '0 2px 8px rgba(0,0,0,.3)',
    });
    document.body.prepend(_bannerEl);
  }
  return _bannerEl;
}

function showBanner(state, count = 0) {
  const b = getBanner();
  const configs = {
    offline:   { bg: '#dc3545', text: `&#x1F6AB; Sem conex\u00e3o \u2014 ${count > 0 ? count + ' opera\u00e7\u00e3o(oes) na fila' : 'trabalhando offline'}` },
    syncing:   { bg: '#fd7e14', text: `<span class="polsec-spinner"></span> Sincronizando ${count} opera\u00e7\u00e3o(oes)...` },
    synced:    { bg: '#198754', text: `&#x2713; Sincronizado com sucesso!` },
    failed:    { bg: '#dc3545', text: `&#x26A0; Algumas opera\u00e7\u00f5es falharam. Verifique a fila.` },
  };
  const cfg = configs[state];
  if (!cfg) { b.style.transform = 'translateY(-100%)'; return; }
  b.style.background = cfg.bg;
  b.style.color = '#fff';
  b.innerHTML = cfg.text;
  b.style.transform = 'translateY(0)';
  if (state === 'synced') setTimeout(() => hideBanner(), 4000);
}

function hideBanner() {
  if (_bannerEl) _bannerEl.style.transform = 'translateY(-100%)';
}

// ── Toast ─────────────────────────────────────────────────────────────────────
function showToast(msg, type = 'info', duration = 5000) {
  let container = document.getElementById('polsec-toasts');
  if (!container) {
    container = document.createElement('div');
    container.id = 'polsec-toasts';
    Object.assign(container.style, {
      position: 'fixed', bottom: '1.2rem', right: '1.2rem', zIndex: '10000',
      display: 'flex', flexDirection: 'column', gap: '8px', maxWidth: '340px',
    });
    document.body.appendChild(container);
  }
  const colors = { info: '#0d6efd', success: '#198754', warning: '#fd7e14', error: '#dc3545' };
  const toast = document.createElement('div');
  Object.assign(toast.style, {
    background: colors[type] || colors.info, color: '#fff',
    padding: '10px 16px', borderRadius: '8px', fontSize: '13px', fontWeight: '500',
    boxShadow: '0 4px 14px rgba(0,0,0,.3)', animation: 'polsec-slidein 0.2s ease',
    lineHeight: '1.4',
  });
  toast.innerHTML = msg;
  container.appendChild(toast);
  setTimeout(() => toast.remove(), duration);
}

// ── Serialização do form ──────────────────────────────────────────────────────
function serializeForm(form) {
  const entries = {};
  new FormData(form).forEach((v, k) => { entries[k] = v; });
  return entries;
}

// ── Interceptação de forms ────────────────────────────────────────────────────
function interceptForms() {
  document.addEventListener('submit', async e => {
    // Nunca interceptar: form de login e forms marcados como no-offline
    const form = e.target;
    if (form.dataset.noOffline !== undefined) return;
    if (form.closest('[data-no-offline]')) return;
    if (!navigator.onLine) {
      e.preventDefault();
      const url    = new URL(form.action || window.location.href);
      const method = (form.getAttribute('method') || 'POST').toUpperCase();
      const body   = serializeForm(form);
      const label  = form.dataset.offlineLabel
        || form.closest('[data-offline-label]')?.dataset.offlineLabel
        || document.title;

      await enqueue({
        url:       url.pathname + url.search,
        method,
        body,
        label,
        timestamp: new Date().toISOString(),
        status:    'pending',
      });

      const total = await countPending();
      showBanner('offline', total);
      showToast(`&#128190; <strong>Salvo localmente</strong><br>${label}<br><small>Sincronizará quando conectar.</small>`, 'warning', 7000);
    }
  });
}

// ── Sync quando reconectar ────────────────────────────────────────────────────
async function syncQueue() {
  const ops = await getPendingOps();
  if (!ops.length) return;

  showBanner('syncing', ops.length);

  let success = 0;
  let failed  = 0;

  for (const op of ops) {
    try {
      const fd = new FormData();
      for (const [k, v] of Object.entries(op.body)) fd.append(k, v);

      const res = await fetch(op.url, { method: op.method, body: fd, redirect: 'follow' });

      // Form HTML retorna 302/200 → considera sucesso
      if (res.ok || res.redirected || (res.status >= 300 && res.status < 400)) {
        await updateOpStatus(op.id, 'synced', { synced_at: new Date().toISOString() });
        success++;
      } else {
        await updateOpStatus(op.id, 'failed', { error: `HTTP ${res.status}` });
        failed++;
      }
    } catch (err) {
      await updateOpStatus(op.id, 'failed', { error: err.message });
      failed++;
    }
  }

  if (failed === 0) {
    showBanner('synced');
    if (success > 0) {
      showToast(`&#x2705; <strong>${success} opera\u00e7\u00e3o(oes) sincronizadas</strong><br>Atualizando a p\u00e1gina...`, 'success', 4000);
      setTimeout(() => window.location.reload(), 3000);
    }
  } else {
    showBanner('failed');
    showToast(`&#x26A0; ${success} sincronizadas, <strong>${failed} com erro</strong>.`, 'error', 8000);
  }
}

// ── Registro do Service Worker ────────────────────────────────────────────────
async function registerSW() {
  if ('serviceWorker' in navigator) {
    try {
      const reg = await navigator.serviceWorker.register('/sw.js', { scope: '/' });
      // Força update imediato quando há novo SW disponível
      reg.addEventListener('updatefound', () => {
        const sw = reg.installing;
        sw?.addEventListener('statechange', () => {
          if (sw.state === 'installed' && navigator.serviceWorker.controller) {
            showToast('&#x1F504; Nova vers\u00e3o dispon\u00edvel \u2014 recarregue a p\u00e1gina.', 'info', 10000);
          }
        });
      });
    } catch (e) {
      console.warn('[POLSEC SW] Registro falhou:', e);
    }
  }
}

// ── Injetar estilos ───────────────────────────────────────────────────────────
function injectStyles() {
  const style = document.createElement('style');
  style.textContent = `
    @keyframes polsec-slidein { from { opacity:0; transform:translateY(8px); } to { opacity:1; transform:translateY(0); } }
    .polsec-spinner {
      display:inline-block; width:12px; height:12px; border:2px solid rgba(255,255,255,.4);
      border-top-color:#fff; border-radius:50%; animation:polsec-spin .7s linear infinite;
    }
    @keyframes polsec-spin { to { transform:rotate(360deg); } }
  `;
  document.head.appendChild(style);
}

// ── Init ──────────────────────────────────────────────────────────────────────
(async function init() {
  injectStyles();
  await registerSW();
  interceptForms();

  // Estado inicial
  if (!navigator.onLine) {
    const total = await countPending();
    showBanner('offline', total);
  }

  // Ouvintes de rede
  window.addEventListener('offline', async () => {
    const total = await countPending();
    showBanner('offline', total);
  });

  window.addEventListener('online', async () => {
    const total = await countPending();
    if (total > 0) {
      await syncQueue();
    } else {
      hideBanner();
    }
  });
})();
