/* ==========================================================================
   craftproofApi.js — CraftProof Passports & Demand Bridge API
   --------------------------------------------------------------------------
   Strictly additive API helpers using relative `/api/v1/...` paths (proxied
   automatically by Vite dev server to FastAPI `:8000` with zero localhost
   hardcoding in browser code).
   ========================================================================== */

const API_BASE = '/api/v1';

async function cpRequest(path, { method = 'GET', token = null, body = null } = {}) {
  const headers = { Accept: 'application/json' };
  if (body !== null) headers['Content-Type'] = 'application/json';
  if (token) headers.Authorization = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers,
    body: body !== null ? JSON.stringify(body) : undefined
  });

  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err = new Error(
      typeof data?.detail === 'string'
        ? data.detail
        : Array.isArray(data?.detail)
          ? data.detail.map((d) => d?.msg || JSON.stringify(d)).join('; ')
          : `Request failed (HTTP ${res.status})`
    );
    err.status = res.status;
    err.payload = data;
    throw err;
  }
  return data;
}

// ---------------------------------------------------------------------------
// Public CraftProof Digital Passports & QR Lookup
// ---------------------------------------------------------------------------
export function fetchPassportByCode(code) {
  return cpRequest(`/passports/${encodeURIComponent(code)}`);
}

export function fetchPassportByProduct(productRef) {
  return cpRequest(`/passports/by-product/${encodeURIComponent(productRef)}`);
}

export function lookupPassports(query) {
  return cpRequest(`/passports/lookup?q=${encodeURIComponent(query)}`);
}

export function passportQrSvgUrl(code) {
  return `${API_BASE}/passports/${encodeURIComponent(code)}/qr.svg`;
}

// ---------------------------------------------------------------------------
// Seller CraftProof Claims & Evidence
// ---------------------------------------------------------------------------
export function createOrGetSellerPassport(listingId, payload, token) {
  return cpRequest(`/seller/passports/for-listing/${encodeURIComponent(listingId)}`, {
    method: 'POST',
    token,
    body: payload || {}
  });
}

export function addSellerCraftClaim(passportId, payload, token) {
  return cpRequest(`/seller/passports/${encodeURIComponent(passportId)}/claims`, {
    method: 'POST',
    token,
    body: payload
  });
}

export function attachSellerClaimEvidence(claimId, payload, token) {
  return cpRequest(`/seller/passports/claims/${encodeURIComponent(claimId)}/evidence`, {
    method: 'POST',
    token,
    body: payload
  });
}

// ---------------------------------------------------------------------------
// Admin Human Verification Desk
// ---------------------------------------------------------------------------
export function fetchAdminCraftClaims(token, statusFilter = '') {
  const qs = statusFilter ? `?status_filter=${encodeURIComponent(statusFilter)}` : '';
  return cpRequest(`/admin/passports/claims${qs}`, { token });
}

export function decideAdminCraftClaim(claimId, payload, token) {
  return cpRequest(`/admin/passports/claims/${encodeURIComponent(claimId)}/decision`, {
    method: 'POST',
    token,
    body: payload
  });
}

// ---------------------------------------------------------------------------
// Pillar 4 — Demand Bridge & Multi-Artisan Cluster Pooling
// ---------------------------------------------------------------------------
export function parseDemandBrief(rawRequestText) {
  return cpRequest('/demand-bridge/parse', {
    method: 'POST',
    body: { raw_request_text: rawRequestText }
  });
}

export function matchDemandBridge(payload, token = null) {
  return cpRequest('/demand-bridge/match', {
    method: 'POST',
    token,
    body: payload
  });
}

export function dispatchDemandInquiries(requestId, payload) {
  return cpRequest(`/demand-bridge/requests/${encodeURIComponent(requestId)}/dispatch-inquiries`, {
    method: 'POST',
    body: payload
  });
}

export function fetchRecentDemandRequests() {
  return cpRequest('/demand-bridge/requests');
}

export function fetchSellerClusterOffers(token) {
  return cpRequest('/seller/demand-bridge/offers', { token });
}

export function respondSellerClusterOffer(matchId, payload, token) {
  return cpRequest(`/seller/demand-bridge/offers/${encodeURIComponent(matchId)}/respond`, {
    method: 'POST',
    token,
    body: payload
  });
}
