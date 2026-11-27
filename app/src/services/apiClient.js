/**
 * HunarLink Unified Frontend <-> FastAPI Backend API Client.
 *
 * Zero-regression environment safety:
 *  1. If VITE_API_BASE_URL is configured (e.g. https://api.hunarlink.example),
 *     all requests target that exact base URL.
 *  2. If running under Vite dev server or preview proxy (DEV / localhost / .e2b.app),
 *     requests use relative URLs (`""`) so Vite proxies `/api`, `/healthz`, `/readyz`
 *     directly to FastAPI without browser localhost calls or CORS breakage.
 *  3. On static hosts like GitHub Pages (`*.github.io`) with no VITE_API_BASE_URL,
 *     `resolveApiBase()` returns `null` so zero failed 404 network calls or console
 *     errors ever happen — the storefront stays cleanly in transparent Static Preview mode.
 */

export class ApiError extends Error {
  constructor(status, message, payload = null) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.payload = payload;
  }
}

export function resolveApiBase() {
  const configured = String(import.meta.env.VITE_API_BASE_URL || '').trim();
  if (configured) {
    return configured.replace(/\/+$/, '');
  }
  if (String(import.meta.env.VITE_ENABLE_SAME_ORIGIN_API || '').trim().toLowerCase() === 'true') {
    return '';
  }
  if (import.meta.env.DEV) {
    return '';
  }
  return null;
}

export function canAttemptBackend() {
  return resolveApiBase() !== null;
}

let _cachedProbe = null;
let _cachedProbeAt = 0;
const PROBE_TTL_MS = 15000;

export async function probeBackendHealth({ force = false } = {}) {
  const base = resolveApiBase();
  if (base === null) {
    return {
      online: false,
      mode: 'static-preview',
      reason: 'Static host without VITE_API_BASE_URL',
      health: null,
      ready: null
    };
  }
  const now = Date.now();
  if (!force && _cachedProbe && now - _cachedProbeAt < PROBE_TTL_MS) {
    return _cachedProbe;
  }

  const controller = typeof AbortController !== 'undefined' ? new AbortController() : null;
  const timer = controller ? setTimeout(() => controller.abort(), 2200) : null;
  try {
    const [healthRes, readyRes] = await Promise.all([
      fetch(`${base}/healthz`, { method: 'GET', signal: controller?.signal }),
      fetch(`${base}/readyz`, { method: 'GET', signal: controller?.signal }).catch(() => null)
    ]);
    if (!healthRes.ok) {
      throw new Error(`HTTP ${healthRes.status}`);
    }
    const contentType = healthRes.headers.get('content-type') || '';
    if (!contentType.includes('application/json')) {
      throw new Error('Non-JSON health response');
    }
    const health = await healthRes.json();
    const ready =
      readyRes && readyRes.ok && (readyRes.headers.get('content-type') || '').includes('application/json')
        ? await readyRes.json().catch(() => null)
        : null;

    _cachedProbe = {
      online: health?.status === 'ok',
      mode: health?.status === 'ok' ? 'fastapi-live' : 'static-preview',
      reason: health?.status === 'ok' ? 'Connected to HunarLink FastAPI backend' : 'Backend unhealthy',
      health,
      ready
    };
  } catch (err) {
    _cachedProbe = {
      online: false,
      mode: 'static-preview',
      reason: err?.message || 'Backend unreachable',
      health: null,
      ready: null
    };
  } finally {
    if (timer) clearTimeout(timer);
    _cachedProbeAt = Date.now();
  }
  return _cachedProbe;
}

export async function apiRequest(path, { method = 'GET', body = undefined, token = null, isFormData = false } = {}) {
  const base = resolveApiBase();
  if (base === null) {
    throw new ApiError(0, 'HunarLink FastAPI backend is not configured on this static host.');
  }

  const headers = {};
  if (!isFormData && body !== undefined) {
    headers['Content-Type'] = 'application/json';
  }
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  const resp = await fetch(`${base}${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : isFormData ? body : JSON.stringify(body)
  });

  const isJson = (resp.headers.get('content-type') || '').includes('application/json');
  const data = isJson ? await resp.json().catch(() => null) : null;

  if (!resp.ok) {
    let detail = `Request failed (HTTP ${resp.status})`;
    if (typeof data?.detail === 'string') {
      detail = data.detail;
    } else if (Array.isArray(data?.detail) && data.detail.length > 0) {
      const first = data.detail[0];
      const field = Array.isArray(first?.loc) ? first.loc[first.loc.length - 1] : '';
      detail = field ? `${field}: ${first.msg}` : first?.msg || detail;
    } else if (data?.detail?.field_errors?.[0]?.message) {
      detail = data.detail.field_errors[0].message;
    } else if (data?.detail?.issues?.[0]?.message) {
      detail = data.detail.issues[0].message;
    }
    throw new ApiError(resp.status, detail, data);
  }
  return data;
}

export async function fetchProtectedBlobUrl(path, token) {
  const base = resolveApiBase();
  if (base === null) {
    throw new ApiError(0, 'HunarLink FastAPI backend is not configured.');
  }
  const resp = await fetch(`${base}${path}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {}
  });
  if (!resp.ok) {
    const isJson = (resp.headers.get('content-type') || '').includes('application/json');
    const data = isJson ? await resp.json().catch(() => null) : null;
    const msg = typeof data?.detail === 'string' ? data.detail : `Could not load document (HTTP ${resp.status})`;
    throw new ApiError(resp.status, msg, data);
  }
  const blob = await resp.blob();
  return {
    blobUrl: URL.createObjectURL(blob),
    mimeType: resp.headers.get('content-type') || blob.type || 'application/octet-stream'
  };
}

/* --- 1:1 Clerk Auth -> DB User Sync & Artisan Onboarding Endpoints --- */
export function syncAuthenticatedUser(payload, token) {
  return apiRequest('/api/v1/auth/sync', { method: 'POST', body: payload, token });
}

export function checkAuthAccount(email, requestedRole = null) {
  const body = { email };
  if (requestedRole) {
    body.requested_role = requestedRole;
  }
  return apiRequest('/api/v1/auth/check-account', {
    method: 'POST',
    body
  });
}

export function fetchMyAuthProfile(token) {
  return apiRequest('/api/v1/auth/me', { token });
}

export function deleteMyAccount(token, { currentPassword = null, reason = null } = {}) {
  const body = {};
  if (currentPassword) body.current_password = currentPassword;
  if (reason) body.reason = reason;
  return apiRequest('/api/v1/auth/me/delete', {
    method: 'POST',
    body,
    token
  });
}

export function submitArtisanVerification(payload, token) {
  return apiRequest('/api/v1/auth/artisan-verification', {
    method: 'POST',
    body: payload,
    token
  });
}

export function fetchMyAddresses(token) {
  return apiRequest('/api/v1/auth/addresses', { token });
}

export function createMyAddress(payload, token) {
  return apiRequest('/api/v1/auth/addresses', { method: 'POST', body: payload, token });
}

export function deleteMyAddress(addressId, token) {
  return apiRequest(`/api/v1/auth/addresses/${encodeURIComponent(addressId)}`, {
    method: 'DELETE',
    token
  });
}

/* --- 1:1 Authenticated Storefront, Artisans & Retail Order Endpoints --- */
export function fetchCatalogProducts(categorySlug = null, token = null) {
  const params = new URLSearchParams({ limit: '200' });
  if (categorySlug) params.set('category_slug', categorySlug);
  return apiRequest(`/api/v1/catalog/products?${params.toString()}`, { token });
}

export function fetchCatalogProductById(productOrListingId, token = null) {
  return apiRequest(`/api/v1/catalog/product?id=${encodeURIComponent(productOrListingId)}`, { token });
}

export function fetchArtisans(token = null) {
  return apiRequest('/api/v1/artisans', { token });
}

export function fetchArtisanById(artisanId, token = null) {
  return apiRequest(`/api/v1/artisans/detail?id=${encodeURIComponent(artisanId)}`, { token });
}

export function fetchArtisanBySlug(slugOrId, token = null) {
  return apiRequest(`/api/v1/artisans/${encodeURIComponent(slugOrId)}`, { token });
}

export function createRetailOrder(payload, token) {
  return apiRequest('/api/v1/orders/retail', { method: 'POST', body: payload, token });
}

export function fetchMyRetailOrders(token) {
  return apiRequest('/api/v1/orders/retail/my', { token });
}

/* --- 1:1 ASIGS Seller & Document Guardrail Endpoints --- */
export function validateSellerListing(payload, token) {
  return apiRequest('/api/v1/seller/listings/validate', { method: 'POST', body: payload, token });
}

export function createSellerListing(payload, token) {
  return apiRequest('/api/v1/seller/listings', { method: 'POST', body: payload, token });
}

export function fetchSellerStudioListings(token) {
  return apiRequest('/api/v1/seller/studio/listings', { token });
}

export function validateSellerStudioListing(payload, token) {
  return apiRequest('/api/v1/seller/studio/validate', { method: 'POST', body: payload, token });
}

export function publishSellerStudioListing(payload, token) {
  return apiRequest('/api/v1/seller/studio/listings', { method: 'POST', body: payload, token });
}

export function moderateAdminListing(listingId, listingStatus, token) {
  return apiRequest(`/api/v1/admin/listings/${encodeURIComponent(listingId)}/moderate`, {
    method: 'POST',
    body: { listing_status: listingStatus },
    token
  });
}

export function decideAdminArtisanApplication(applicationId, { decision, notes }, token) {
  return apiRequest(
    `/api/v1/admin/artisan-applications/${encodeURIComponent(applicationId)}/decision`,
    {
      method: 'POST',
      body: { decision, notes: notes || null },
      token
    }
  );
}

export function fetchGuardrailDocumentBlobUrl(scanId, token) {
  return fetchProtectedBlobUrl(`/api/v1/guardrails/documents/${encodeURIComponent(scanId)}`, token);
}

export function verifyAdminSeller(sellerId, decision, token) {
  return apiRequest(`/api/v1/admin/sellers/${encodeURIComponent(sellerId)}/verify`, {
    method: 'POST',
    body: { decision },
    token
  });
}

export function uploadGuardrailDocument(file, ownerScope, token) {
  const form = new FormData();
  form.append('owner_scope', ownerScope || 'seller_document');
  form.append('file', file);
  return apiRequest('/api/v1/guardrails/documents/upload', {
    method: 'POST',
    body: form,
    token,
    isFormData: true
  });
}

/* --- 1:1 Admin Guardrail Center Endpoints --- */
export function fetchAdminGuardrailCases(token, caseStatus = null) {
  const qs = caseStatus ? `?case_status=${encodeURIComponent(caseStatus)}` : '';
  return apiRequest(`/api/v1/admin/guardrail/cases${qs}`, { token });
}

export function decideAdminGuardrailCase(caseId, payload, token) {
  return apiRequest(`/api/v1/admin/guardrail/cases/${encodeURIComponent(caseId)}/decision`, {
    method: 'POST',
    body: payload,
    token
  });
}

export function fetchAdminGuardrailRules(token) {
  return apiRequest('/api/v1/admin/guardrail/rules', { token });
}

/* --- 1:1 Dedicated Admin Email + Password Login & Overview Endpoints --- */
export function adminPasswordLogin({ email, password }) {
  return apiRequest('/api/v1/auth/admin-login', {
    method: 'POST',
    body: { email, password }
  });
}

export function fetchAdminOverview(token) {
  return apiRequest('/api/v1/admin/overview', { token });
}

export function fetchAdminUsersByRole(token, { roleCode = null, activity = 'all' } = {}) {
  const params = new URLSearchParams();
  if (roleCode) params.set('role_code', roleCode);
  if (activity) params.set('activity', activity);
  const qs = params.toString() ? `?${params.toString()}` : '';
  return apiRequest(`/api/v1/admin/users-by-role${qs}`, { token });
}

export function deleteAdminUser(userId, { reason = null } = {}, token) {
  const body = {};
  if (reason) body.reason = reason;
  return apiRequest(`/api/v1/admin/users/${encodeURIComponent(userId)}/delete`, {
    method: 'POST',
    body,
    token
  });
}

export function fetchAdminPayments(token, { orderScope = null, paymentStatus = null } = {}) {
  const params = new URLSearchParams();
  if (orderScope) params.set('order_scope', orderScope);
  if (paymentStatus) params.set('payment_status', paymentStatus);
  const qs = params.toString() ? `?${params.toString()}` : '';
  return apiRequest(`/api/v1/admin/payments${qs}`, { token });
}

export function fetchAdminPaymentWebhooks(token) {
  return apiRequest('/api/v1/admin/payment-webhooks', { token });
}

export function fetchAdminRefunds(token) {
  return apiRequest('/api/v1/admin/refunds', { token });
}

export function initiateAdminRefund(paymentId, payload, token) {
  return apiRequest(`/api/v1/payments/${encodeURIComponent(paymentId)}/refund`, {
    method: 'POST',
    body: payload,
    token
  });
}
