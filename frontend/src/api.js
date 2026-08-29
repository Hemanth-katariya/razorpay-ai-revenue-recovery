/* ═══════════════════════════════════════════════════
   RecoverFlow Dashboard — API Client
   ═══════════════════════════════════════════════════ */

const API_BASE = 'http://127.0.0.1:8000';

export async function apiFetch(path, opts = {}) {
  const url = `${API_BASE}${path}`;
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json', ...opts.headers },
    ...opts,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `API error ${res.status}`);
  }
  return res.json();
}

export async function healthCheck() {
  try {
    await apiFetch('/health');
    return true;
  } catch { return false; }
}

// Batches
export const getBatches = () => apiFetch('/batches');
export const createBatch = (data) => apiFetch('/batches', { method: 'POST', body: JSON.stringify(data) });
export const closeBatch = (id, data = {}) => apiFetch(`/batches/${id}/close`, { method: 'POST', body: JSON.stringify(data) });
export const getMetrics = (id) => apiFetch(`/batches/${id}/metrics`);

// Subscriptions
export const getSubscriptions = (batchId) => apiFetch(`/subscriptions?batch_run_id=${batchId}`);
export const getAuditTrail = (subId) => apiFetch(`/subscriptions/${subId}/audit`);

// Escalations
export const getEscalations = (status = 'open') => apiFetch(`/escalations?status=${status}`);
export const resolveEscalation = (id, data) => apiFetch(`/escalations/${id}/resolve`, { method: 'POST', body: JSON.stringify(data) });
