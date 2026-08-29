/* ═══════════════════════════════════════════════════
   RecoverFlow Dashboard — Main Application
   ═══════════════════════════════════════════════════ */
import './style.css';
import * as api from './api.js';

// ─── State ───────────────────────────────────────
let currentView = 'pipeline';
let currentBatchId = null;
let subscriptions = [];
let selectedSubId = null;

// ─── Helpers ─────────────────────────────────────
function formatPaise(paise) {
  if (!paise && paise !== 0) return '₹0';
  return '₹' + (paise / 100).toLocaleString('en-IN', { minimumFractionDigits: 0, maximumFractionDigits: 0 });
}

function formatPercent(n) {
  return (n * 100).toFixed(1) + '%';
}

function truncateId(id) {
  if (!id) return '—';
  return id.length > 12 ? id.slice(0, 12) + '…' : id;
}

function stateBadge(state) {
  return `<span class="state-badge ${state}">${state.replace('_', ' ')}</span>`;
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

// ─── Navigation ──────────────────────────────────
document.querySelectorAll('.nav-item').forEach(btn => {
  btn.addEventListener('click', () => {
    const view = btn.dataset.view;
    switchView(view);
  });
});

function switchView(view) {
  currentView = view;
  document.querySelectorAll('.nav-item').forEach(b => b.classList.toggle('active', b.dataset.view === view));
  document.querySelectorAll('.view').forEach(v => v.classList.toggle('active', v.id === `view-${view}`));
  loadViewData(view);
}

async function loadViewData(view) {
  if (!currentBatchId) return;
  try {
    switch (view) {
      case 'pipeline': await loadPipeline(); break;
      case 'subscriptions': await loadSubscriptionsList(); break;
      case 'metrics': await loadMetrics(); break;
      case 'escalations': await loadEscalations(); break;
      case 'audit': break; // loaded when subscription is selected
    }
  } catch (e) {
    console.error('Failed to load view data:', e);
  }
}

// ─── API Status Check ────────────────────────────
async function checkApiStatus() {
  const statusEl = document.getElementById('api-status');
  const online = await api.healthCheck();
  statusEl.innerHTML = online
    ? '<span class="status-dot online"></span><span>API Connected</span>'
    : '<span class="status-dot offline"></span><span>API Disconnected</span>';
  return online;
}

// ─── Batch Selector ──────────────────────────────
const batchSelect = document.getElementById('batch-select');

async function loadBatches() {
  try {
    const batches = await api.getBatches();
    batchSelect.innerHTML = batches.length
      ? batches.map(b => `<option value="${b.id}">${escapeHtml(b.label)} (${b.status})</option>`).join('')
      : '<option value="">No batches</option>';
    if (batches.length) {
      currentBatchId = batches[batches.length - 1].id; // latest
      batchSelect.value = currentBatchId;
      loadViewData(currentView);
    }
  } catch {
    batchSelect.innerHTML = '<option value="">Failed to load</option>';
  }
}

batchSelect.addEventListener('change', (e) => {
  currentBatchId = e.target.value;
  if (currentBatchId) loadViewData(currentView);
});

// ─── Pipeline View ───────────────────────────────
async function loadPipeline() {
  if (!currentBatchId) return;

  subscriptions = await api.getSubscriptions(currentBatchId);

  // Update flow counts
  const counts = {};
  for (const s of subscriptions) {
    counts[s.current_state] = (counts[s.current_state] || 0) + 1;
  }
  const states = ['DETECTED', 'DIAGNOSED', 'GATED', 'EXECUTING', 'ESCALATED', 'STOPPED', 'RECOVERED', 'NOT_RECOVERED'];
  for (const st of states) {
    const el = document.getElementById(`flow-${st.toLowerCase().replace('_', '-')}`);
    if (el) {
      const oldVal = parseInt(el.textContent) || 0;
      const newVal = counts[st] || 0;
      el.textContent = newVal;
      if (newVal !== oldVal) {
        el.parentElement.style.animation = 'none';
        el.parentElement.offsetHeight; // reflow
        el.parentElement.style.animation = 'fadeIn 0.4s ease';
      }
    }
  }

  // Update stat cards
  let metrics;
  try {
    metrics = await api.getMetrics(currentBatchId);
  } catch { metrics = null; }

  if (metrics) {
    document.getElementById('stat-at-risk').textContent = formatPaise(metrics.revenue_at_risk_detected.amount_paise);
    document.getElementById('stat-at-risk-count').textContent = `${metrics.revenue_at_risk_detected.count} subscriptions`;
    document.getElementById('stat-recovered').textContent = formatPaise(metrics.revenue_recovered.amount_paise);
    document.getElementById('stat-recovered-rate').textContent = `${formatPercent(metrics.recovery_rate.recovered_over_detected)} recovery rate`;
    document.getElementById('stat-escalated').textContent = metrics.escalation_rate.count;
    document.getElementById('stat-escalated-rate').textContent = `${formatPercent(metrics.escalation_rate.share_of_batch)} of batch`;
    document.getElementById('stat-stopped').textContent = metrics.stop_rate.count;
    document.getElementById('stat-stopped-rate').textContent = `${formatPercent(metrics.stop_rate.share_of_batch)} of batch`;
  }

  // Update table
  const tbody = document.getElementById('pipeline-tbody');
  const empty = document.getElementById('pipeline-empty');

  if (subscriptions.length === 0) {
    tbody.innerHTML = '';
    empty.style.display = 'flex';
    return;
  }
  empty.style.display = 'none';

  tbody.innerHTML = subscriptions.map(s => `
    <tr>
      <td><span style="font-family:var(--font-mono);color:var(--text-accent);font-size:0.82rem">${escapeHtml(s.id)}</span></td>
      <td>${escapeHtml(s.customer_ref)}</td>
      <td style="font-variant-numeric:tabular-nums;font-weight:600">${formatPaise(s.outstanding_amount)}</td>
      <td>${stateBadge(s.current_state)}</td>
      <td style="text-align:center">${s.attempt_count}</td>
      <td>
        <button class="btn btn-sm btn-secondary view-audit-btn" data-sub-id="${s.id}">
          Audit Trail
        </button>
      </td>
    </tr>
  `).join('');

  tbody.querySelectorAll('.view-audit-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      selectedSubId = btn.dataset.subId;
      switchView('subscriptions');
    });
  });

  // Update escalation badge
  try {
    const escs = await api.getEscalations('open');
    const badge = document.getElementById('esc-badge');
    if (escs.length > 0) {
      badge.textContent = escs.length;
      badge.style.display = 'inline-flex';
    } else {
      badge.style.display = 'none';
    }
  } catch { /* ignore */ }
}

// ─── Subscriptions View ──────────────────────────
async function loadSubscriptionsList() {
  if (!currentBatchId) return;
  if (!subscriptions.length) {
    subscriptions = await api.getSubscriptions(currentBatchId);
  }

  const list = document.getElementById('sub-list');
  if (subscriptions.length === 0) {
    list.innerHTML = '<div class="empty-state"><p>No subscriptions in this batch</p></div>';
    return;
  }

  list.innerHTML = subscriptions.map(s => `
    <div class="sub-list-item ${s.id === selectedSubId ? 'active' : ''}" data-sub-id="${s.id}">
      <span class="sub-id">${escapeHtml(s.id)}</span>
      <span class="sub-customer">${escapeHtml(s.customer_ref)}</span>
      <div style="display:flex;align-items:center;justify-content:space-between;margin-top:4px">
        <span class="sub-amount">${formatPaise(s.outstanding_amount)}</span>
        ${stateBadge(s.current_state)}
      </div>
    </div>
  `).join('');

  list.querySelectorAll('.sub-list-item').forEach(item => {
    item.addEventListener('click', () => {
      selectedSubId = item.dataset.subId;
      list.querySelectorAll('.sub-list-item').forEach(i => i.classList.remove('active'));
      item.classList.add('active');
      loadAuditTrail(selectedSubId);
    });
  });

  if (selectedSubId) {
    loadAuditTrail(selectedSubId);
  }
}

async function loadAuditTrail(subId) {
  const detail = document.getElementById('sub-detail');
  try {
    const data = await api.getAuditTrail(subId);

    const sub = subscriptions.find(s => s.id === subId);
    const header = `
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:20px">
        <div>
          <h3 style="font-size:1.1rem;margin-bottom:4px">${escapeHtml(sub?.customer_ref || subId)}</h3>
          <span style="font-family:var(--font-mono);font-size:0.82rem;color:var(--text-muted)">${subId}</span>
        </div>
        <div style="text-align:right">
          ${stateBadge(data.current_state)}
          <div style="font-size:0.82rem;color:var(--text-secondary);margin-top:4px">${formatPaise(sub?.outstanding_amount)}</div>
        </div>
      </div>
    `;

    if (data.trail.length === 0) {
      detail.innerHTML = header + '<div class="empty-state"><p>No audit entries yet</p></div>';
      return;
    }

    const timeline = data.trail.map(entry => {
      const detailStr = JSON.stringify(entry.detail, null, 2);
      return `
        <div class="audit-entry ${entry.actor}">
          <div class="audit-entry-header">
            <span class="audit-entry-actor ${entry.actor}">${entry.actor}</span>
            <span class="audit-entry-ts">${entry.ts}</span>
          </div>
          <div class="audit-transition">
            ${entry.prior_state ? stateBadge(entry.prior_state) : '<span class="state-badge" style="opacity:0.4">NEW</span>'}
            <span style="color:var(--text-muted)">→</span>
            ${stateBadge(entry.new_state)}
          </div>
          <div class="audit-detail">${escapeHtml(detailStr)}</div>
        </div>
      `;
    }).join('');

    detail.innerHTML = header + `<div class="audit-timeline">${timeline}</div>`;
  } catch (e) {
    detail.innerHTML = `<div class="empty-state"><p>Failed to load audit trail: ${escapeHtml(e.message)}</p></div>`;
  }
}

// ─── Metrics View ────────────────────────────────
async function loadMetrics() {
  if (!currentBatchId) return;
  const container = document.getElementById('metrics-content');

  try {
    const m = await api.getMetrics(currentBatchId);

    const maxConfCount = Math.max(1, ...Object.values(m.diagnosis_confidence_distribution));

    container.innerHTML = `
      <div class="stat-cards" style="margin-bottom:24px">
        <div class="stat-card">
          <div class="stat-label">Revenue at Risk</div>
          <div class="stat-value">${formatPaise(m.revenue_at_risk_detected.amount_paise)}</div>
          <div class="stat-sub">${m.revenue_at_risk_detected.count} subscriptions detected</div>
        </div>
        <div class="stat-card accent">
          <div class="stat-label">Revenue Recovered</div>
          <div class="stat-value">${formatPaise(m.revenue_recovered.amount_paise)}</div>
          <div class="stat-sub">${m.revenue_recovered.count} subscriptions recovered</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Recovery Rate</div>
          <div class="stat-value" style="color:var(--cyan)">${formatPercent(m.recovery_rate.recovered_over_detected)}</div>
          <div class="stat-sub">of detected • ${formatPercent(m.recovery_rate.recovered_over_attempted)} of attempted</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Avg Time to Recovery</div>
          <div class="stat-value" style="color:var(--accent-light)">${m.time_to_recovery_seconds_avg != null ? (m.time_to_recovery_seconds_avg / 3600).toFixed(1) + 'h' : 'N/A'}</div>
          <div class="stat-sub">logical time (simulated)</div>
        </div>
      </div>

      <div class="metrics-grid">
        <!-- Escalation Breakdown -->
        <div class="metric-card">
          <h4>Escalation Breakdown</h4>
          <div class="metric-big-number" style="color:var(--warning)">${m.escalation_rate.count}</div>
          <div class="stat-sub">${formatPercent(m.escalation_rate.share_of_batch)} of batch</div>
          <div class="bar-chart">
            ${Object.entries(m.escalation_rate.by_reason || {}).map(([reason, count]) => `
              <div class="bar-row">
                <span class="bar-label">${reason}</span>
                <div class="bar-track">
                  <div class="bar-fill warning" style="width:${(count / Math.max(1, m.escalation_rate.count)) * 100}%"></div>
                </div>
                <span class="bar-value">${count}</span>
              </div>
            `).join('') || '<div style="color:var(--text-muted);font-size:0.82rem">No escalations</div>'}
          </div>
        </div>

        <!-- Stop Breakdown -->
        <div class="metric-card">
          <h4>Stop Breakdown</h4>
          <div class="metric-big-number" style="color:var(--danger)">${m.stop_rate.count}</div>
          <div class="stat-sub">${formatPercent(m.stop_rate.share_of_batch)} of batch</div>
          <div class="bar-chart">
            ${Object.entries(m.stop_rate.by_reason || {}).map(([reason, count]) => `
              <div class="bar-row">
                <span class="bar-label">${reason}</span>
                <div class="bar-track">
                  <div class="bar-fill danger" style="width:${(count / Math.max(1, m.stop_rate.count)) * 100}%"></div>
                </div>
                <span class="bar-value">${count}</span>
              </div>
            `).join('') || '<div style="color:var(--text-muted);font-size:0.82rem">No stops</div>'}
          </div>
        </div>

        <!-- Confidence Distribution -->
        <div class="metric-card">
          <h4>AI Diagnosis Confidence</h4>
          <div class="bar-chart">
            ${Object.entries(m.diagnosis_confidence_distribution || {}).sort().map(([bucket, count]) => `
              <div class="bar-row">
                <span class="bar-label">${bucket}</span>
                <div class="bar-track">
                  <div class="bar-fill accent" style="width:${(count / maxConfCount) * 100}%"></div>
                </div>
                <span class="bar-value">${count}</span>
              </div>
            `).join('') || '<div style="color:var(--text-muted);font-size:0.82rem">No diagnoses</div>'}
          </div>
        </div>
      </div>

      <!-- Reconciliation -->
      <div class="reconciliation">
        <h4>Batch Size Reconciliation (Acceptance Criterion #7)</h4>
        <div class="recon-equation">
          <span class="recon-term" style="background:rgba(52,211,153,0.15);color:var(--recovered)">Recovered: ${m.batch_size_reconciliation.recovered}</span>
          <span class="recon-op">+</span>
          <span class="recon-term" style="background:rgba(248,113,113,0.15);color:var(--stopped)">Stopped: ${m.batch_size_reconciliation.stopped}</span>
          <span class="recon-op">+</span>
          <span class="recon-term" style="background:rgba(107,114,128,0.15);color:var(--not-recovered)">Not Recovered: ${m.batch_size_reconciliation.not_recovered}</span>
          <span class="recon-op">+</span>
          <span class="recon-term" style="background:rgba(251,191,36,0.15);color:var(--escalated)">Still Open: ${m.batch_size_reconciliation.still_open}</span>
          <span class="recon-op">=</span>
          <span class="recon-term" style="background:rgba(129,140,248,0.15);color:var(--accent-light);font-weight:700">Total: ${m.batch_size_reconciliation.total}</span>
        </div>
      </div>
    `;
  } catch (e) {
    container.innerHTML = `<div class="empty-state"><p>Failed to load metrics: ${escapeHtml(e.message)}</p></div>`;
  }
}

// ─── Escalations View ────────────────────────────
async function loadEscalations() {
  const container = document.getElementById('escalations-content');

  try {
    const openEscs = await api.getEscalations('open');
    const resolvedEscs = await api.getEscalations('resolved');
    const all = [...openEscs, ...resolvedEscs];

    if (all.length === 0) {
      container.innerHTML = `
        <div class="empty-state">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
          <p>No escalations in this batch</p>
        </div>`;
      return;
    }

    container.innerHTML = `
      <div class="escalation-list">
        ${all.map(e => `
          <div class="escalation-card ${e.status === 'resolved' ? 'resolved' : ''}">
            <div class="esc-info">
              <span class="esc-sub-id">${escapeHtml(e.subscription_id)}</span>
              <span class="esc-reason">Reason: <strong>${escapeHtml(e.reason)}</strong></span>
              <span class="esc-time">Opened: ${e.opened_at}${e.resolved_at ? ` • Resolved: ${e.resolved_at}` : ''}</span>
              ${e.resolution ? `<span class="esc-time">Resolution: <strong>${e.resolution}</strong>${e.resolver_note ? ` — ${escapeHtml(e.resolver_note)}` : ''}</span>` : ''}
            </div>
            <div>
              ${e.status === 'open' ? `<button class="btn btn-sm btn-warning resolve-btn" data-esc-id="${e.id}" data-sub-id="${e.subscription_id}">Resolve</button>` : `<span class="state-badge ${e.resolution === 'recovered' ? 'RECOVERED' : 'NOT_RECOVERED'}">${e.resolution || 'resolved'}</span>`}
            </div>
          </div>
        `).join('')}
      </div>
    `;

    container.querySelectorAll('.resolve-btn').forEach(btn => {
      btn.addEventListener('click', () => openResolveModal(btn.dataset.escId, btn.dataset.subId));
    });
  } catch (e) {
    container.innerHTML = `<div class="empty-state"><p>Failed to load escalations: ${escapeHtml(e.message)}</p></div>`;
  }
}

// ─── Resolve Modal ───────────────────────────────
let resolveEscId = null;

function openResolveModal(escId, subId) {
  resolveEscId = escId;
  document.getElementById('resolve-modal-info').textContent = `Resolving escalation for subscription ${subId}`;
  document.getElementById('resolve-resolution').value = 'recovered';
  document.getElementById('resolve-note').value = '';
  document.getElementById('resolve-modal').style.display = 'flex';
}

document.getElementById('resolve-cancel').addEventListener('click', () => {
  document.getElementById('resolve-modal').style.display = 'none';
});

document.getElementById('resolve-confirm').addEventListener('click', async () => {
  if (!resolveEscId) return;
  const resolution = document.getElementById('resolve-resolution').value;
  const note = document.getElementById('resolve-note').value || null;

  try {
    await api.resolveEscalation(resolveEscId, { resolution, note });
    document.getElementById('resolve-modal').style.display = 'none';
    await loadEscalations();
    // refresh pipeline too
    subscriptions = [];
    if (currentView === 'pipeline') await loadPipeline();
  } catch (e) {
    alert('Failed to resolve: ' + e.message);
  }
});

// ─── Refresh Button ──────────────────────────────
document.getElementById('btn-refresh').addEventListener('click', () => {
  subscriptions = [];
  loadViewData(currentView);
});

// ─── Init ────────────────────────────────────────
async function init() {
  const online = await checkApiStatus();
  if (online) {
    await loadBatches();
  }
  // Re-check every 5s
  setInterval(async () => {
    const isOnline = await checkApiStatus();
    if (isOnline && !currentBatchId) {
      await loadBatches();
    }
  }, 5000);
}

init();
