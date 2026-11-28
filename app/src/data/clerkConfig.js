import { createContext, useContext } from 'react';

/* ==========================================================================
   clerkConfig — zero-SDK detection + bridge context
   --------------------------------------------------------------------------
   Kept separate from @clerk/react so storefront and GitHub Pages builds
   without VITE_CLERK_PUBLISHABLE_KEY never import or bundle the Clerk SDK.
   ========================================================================== */

const rawKey = String(import.meta.env.VITE_CLERK_PUBLISHABLE_KEY || '').trim();
const isValidKey =
  /^pk_(test|live)_[A-Za-z0-9_+/$=-]{12,}$/.test(rawKey) &&
  !rawKey.includes('your_publishable_key');

export const CLERK_PUBLISHABLE_KEY = isValidKey ? rawKey : '';
export const IS_CLERK_DEV_KEY = CLERK_PUBLISHABLE_KEY.startsWith('pk_test_');

export function isLocalhost() {
  if (typeof window === 'undefined') return false;
  const host = window.location.hostname;
  return host === 'localhost' || host === '127.0.0.1' || host === '[::1]';
}

/* On localhost a pk_test_ (or pk_live_) key mounts Clerk; on public hosts a
   pk_live_ key mounts Clerk, whereas a pk_test_ key is kept for localhost so
   public GitHub Pages visitors aren't blocked by dev_browser_unauthenticated. */
export const HAS_CLERK = Boolean(
  CLERK_PUBLISHABLE_KEY && (!IS_CLERK_DEV_KEY || isLocalhost())
);

export const CLERK_PENDING_ROLE_KEY = 'hunarlink_clerk_pending_role';
export const CLERK_PENDING_AUTH_MODE_KEY = 'hunarlink_clerk_pending_auth_mode';
export const CLERK_ROLE_MAP_KEY = 'hunarlink_clerk_role_map';
export const CLERK_ARTISAN_PROFILES_KEY = 'hunarlink_clerk_artisan_profiles';

export function setPendingClerkAuthMode(mode) {
  if (!mode) return;
  try {
    window.sessionStorage.setItem(CLERK_PENDING_AUTH_MODE_KEY, mode);
  } catch {
    /* ignore */
  }
  try {
    window.localStorage.setItem(CLERK_PENDING_AUTH_MODE_KEY, mode);
  } catch {
    /* ignore */
  }
}

export function readPendingClerkAuthMode() {
  try {
    const s = window.sessionStorage.getItem(CLERK_PENDING_AUTH_MODE_KEY);
    if (s) return s;
  } catch {
    /* ignore */
  }
  try {
    return window.localStorage.getItem(CLERK_PENDING_AUTH_MODE_KEY);
  } catch {
    return null;
  }
}

export function clearPendingClerkAuthMode() {
  try {
    window.sessionStorage.removeItem(CLERK_PENDING_AUTH_MODE_KEY);
  } catch {
    /* ignore */
  }
  try {
    window.localStorage.removeItem(CLERK_PENDING_AUTH_MODE_KEY);
  } catch {
    /* ignore */
  }
}

export function setPendingClerkRole(role) {
  if (!role) return;
  try {
    window.sessionStorage.setItem(CLERK_PENDING_ROLE_KEY, role);
  } catch {
    /* ignore */
  }
  try {
    window.localStorage.setItem(CLERK_PENDING_ROLE_KEY, role);
  } catch {
    /* ignore */
  }
}

export function readPendingClerkRole() {
  try {
    const s = window.sessionStorage.getItem(CLERK_PENDING_ROLE_KEY);
    if (s) return s;
  } catch {
    /* ignore */
  }
  try {
    return window.localStorage.getItem(CLERK_PENDING_ROLE_KEY);
  } catch {
    return null;
  }
}

export function clearPendingClerkRole() {
  try {
    window.sessionStorage.removeItem(CLERK_PENDING_ROLE_KEY);
  } catch {
    /* ignore */
  }
  try {
    window.localStorage.removeItem(CLERK_PENDING_ROLE_KEY);
  } catch {
    /* ignore */
  }
}

export function readClerkArtisanProfile(clerkUserId) {
  if (!clerkUserId) return null;
  try {
    const raw = window.localStorage.getItem(CLERK_ARTISAN_PROFILES_KEY);
    const map = raw ? JSON.parse(raw) : {};
    return map[clerkUserId] || null;
  } catch {
    return null;
  }
}

export function saveClerkArtisanProfile(clerkUserId, profile) {
  if (!clerkUserId || !profile) return;
  try {
    const raw = window.localStorage.getItem(CLERK_ARTISAN_PROFILES_KEY);
    const map = raw ? JSON.parse(raw) : {};
    map[clerkUserId] = { ...(map[clerkUserId] || {}), ...profile };
    window.localStorage.setItem(CLERK_ARTISAN_PROFILES_KEY, JSON.stringify(map));
  } catch {
    /* ignore */
  }
}

export const DEFAULT_CLERK_BRIDGE = {
  enabled: false,
  isLoaded: true,
  isSignedIn: false,
  clerkUser: null,
  getToken: async () => null,
  authenticateWithOAuth: null,
  sendEmailCode: null,
  verifyEmailCode: null,
  signInWithPassword: null,
  sendPasswordResetCode: null,
  completePasswordReset: null,
  signOutClerk: null,
  sendDeleteVerificationCode: null,
  deleteMyAccount: null,
  renderSsoCallback: null
};

export const ClerkBridgeContext = createContext(DEFAULT_CLERK_BRIDGE);

export function useClerkBridge() {
  return useContext(ClerkBridgeContext);
}
