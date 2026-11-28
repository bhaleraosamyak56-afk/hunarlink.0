/**
 * Sanitize client-side post-auth redirect targets so open-redirect URLs
 * (`//evil.com`, `https://evil.com`, `javascript:...`, `/\evil.com`) are rejected.
 */
export function sanitizeInternalRedirect(raw, fallback = '/') {
  if (!raw || typeof raw !== 'string') return fallback;
  const trimmed = raw.trim();
  if (!trimmed.startsWith('/') || trimmed.startsWith('//') || trimmed.startsWith('/\\')) {
    return fallback;
  }
  if (/[\u0000-\u001f]/.test(trimmed)) {
    return fallback;
  }
  try {
    const parsed = new URL(trimmed, 'https://hunarlink.internal');
    if (parsed.origin !== 'https://hunarlink.internal') {
      return fallback;
    }
    return `${parsed.pathname}${parsed.search}${parsed.hash}`;
  } catch {
    return fallback;
  }
}
