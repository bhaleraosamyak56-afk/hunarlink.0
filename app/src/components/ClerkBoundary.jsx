import React, { useCallback, useEffect, useMemo, useRef } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import {
  ClerkProvider,
  useAuth,
  useClerk,
  useSession,
  useUser
} from '@clerk/react';
import { useSignIn, useSignUp } from '@clerk/react/legacy';
import { useStore } from '../state/StoreContext.jsx';
import {
  SESSION_EVENTS_CHANNEL,
  SESSION_REVOKED_STORAGE_KEY,
  canAttemptBackend,
  checkAuthAccount,
  deleteMyAccount as deleteMyAccountApi,
  fetchMyAuthProfile,
  setAuthRevokedHandler,
  syncAuthenticatedUser
} from '../services/apiClient.js';
import {
  CLERK_PUBLISHABLE_KEY,
  CLERK_ROLE_MAP_KEY,
  ClerkBridgeContext,
  clearPendingClerkAuthMode,
  clearPendingClerkRole,
  readClerkArtisanProfile,
  readPendingClerkAuthMode,
  readPendingClerkRole,
  saveClerkArtisanProfile,
  setPendingClerkAuthMode,
  setPendingClerkRole
} from '../data/clerkConfig.js';
import { sanitizeInternalRedirect } from '../utils/safeRedirect.js';
import { evaluatePassword } from '../utils/passwordPolicy.js';

/* ==========================================================================
   ClerkBoundary — the single file in the app that imports @clerk/react
   --------------------------------------------------------------------------
   Lazy-loaded by main.jsx only when HAS_CLERK is true (e.g. localhost with
   VITE_CLERK_PUBLISHABLE_KEY in app/.env.local). Keeps StoreContext in step
   with the Clerk session and powers Google / Apple OAuth on /login and /auth.
   ========================================================================== */

function readRoleMap() {
  try {
    const raw = window.localStorage.getItem(CLERK_ROLE_MAP_KEY);
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}

function saveUserRole(clerkUserId, role) {
  if (!clerkUserId || !role) return;
  try {
    const map = readRoleMap();
    map[clerkUserId] = role;
    window.localStorage.setItem(CLERK_ROLE_MAP_KEY, JSON.stringify(map));
  } catch {
    /* storage unavailable — non-fatal */
  }
}

function initialsOf(first, last, email) {
  const a = (first || email || 'H')[0] || 'H';
  const b = (last || (first && first[1]) || 'L')[0] || 'L';
  return (a + b).toUpperCase();
}

function formatClerkError(err, provider) {
  const first = err?.errors?.[0];
  const code = first?.code || '';
  const msg = first?.longMessage || first?.message || err?.message || '';
  const origin = typeof window !== 'undefined' ? window.location.origin : 'this origin';
  if (code === 'dev_browser_unauthenticated') {
    return `Clerk dev mode requires using the same browser where you are signed into dashboard.clerk.com on ${origin}.`;
  }
  if (/not enabled|unsupported|strategy/i.test(msg)) {
    return `${provider} sign-in is not enabled yet in your Clerk Dashboard (User & Authentication -> SSO Connections).`;
  }
  return msg || `Could not start ${provider} sign-in with Clerk.`;
}

function buildSyncedUser(clerkUser, resolvedRole) {
  const email = clerkUser.primaryEmailAddress?.emailAddress || '';
  const phone = clerkUser.primaryPhoneNumber?.phoneNumber || '';
  const first =
    clerkUser.firstName ||
    (clerkUser.fullName ? clerkUser.fullName.split(' ')[0] : '') ||
    (email ? email.split('@')[0] : 'Collector');
  const last =
    clerkUser.lastName ||
    (clerkUser.fullName ? clerkUser.fullName.split(' ').slice(1).join(' ') : '');
  const fullName = clerkUser.fullName || `${first} ${last}`.trim();
  const badge = initialsOf(first, last, email);

  if (resolvedRole === 'artisan') {
    const saved = readClerkArtisanProfile(clerkUser.id);
    const artisanVerified = Boolean(saved?.artisanVerified);
    return {
      first,
      last,
      fullName,
      email,
      phone: saved?.phone || phone,
      badge,
      artisanVerified,
      payload: {
        name: saved?.name || fullName || first,
        fullName: saved?.name || fullName,
        email: saved?.email || email,
        phone: saved?.phone || phone,
        role: 'artisan',
        artisanVerified,
        business: saved?.business || '',
        craft: saved?.craft || '',
        district: saved?.district || '',
        cluster: saved?.district || '',
        giCertified: Boolean(saved?.giCertified),
        giId: saved?.giId || null,
        skillDescription: saved?.skillDescription || '',
        title: artisanVerified
          ? saved?.title || 'Verified Artisan \u2022 Clerk SSO'
          : 'Artisan Verification Pending \u2022 Clerk SSO',
        badge,
        avatarPhoto: clerkUser.imageUrl || '',
        clerkUserId: clerkUser.id,
        authProvider: 'clerk',
        isLoggedIn: true
      }
    };
  }

  return {
    first,
    last,
    fullName,
    email,
    phone,
    badge,
    artisanVerified: false,
    payload: {
      name: first,
      fullName,
      email,
      phone,
      role: 'buyer',
      title: 'Verified Valley Buyer \u2022 Clerk SSO',
      badge,
      avatarPhoto: clerkUser.imageUrl || '',
      clerkUserId: clerkUser.id,
      authProvider: 'clerk',
      isLoggedIn: true
    }
  };
}

function SsoCallbackRunner() {
  const clerk = useClerk();
  const navigate = useNavigate();
  const ranRef = useRef(false);
  const doneRef = useRef(false);

  useEffect(() => {
    const pendingRole = readPendingClerkRole();
    const pendingMode = readPendingClerkAuthMode();
    const isSignInAttempt = pendingMode !== 'signup';
    const dest = pendingRole === 'artisan' ? '/auth?tab=verify' : '/login';
    const registerDest =
      pendingRole === 'artisan'
        ? '/auth?mode=register&not_registered=1'
        : '/register?not_registered=1';
    const fallbackAuthDest =
      pendingRole === 'artisan'
        ? `/auth?mode=${isSignInAttempt ? 'signin' : 'register'}`
        : isSignInAttempt
          ? '/login'
          : '/register';

    const safetyTimer = window.setTimeout(() => {
      if (doneRef.current) return;
      doneRef.current = true;
      if (clerk?.user) {
        navigate(dest, { replace: true });
      } else {
        clearPendingClerkRole();
        clearPendingClerkAuthMode();
        navigate(isSignInAttempt ? registerDest : fallbackAuthDest, { replace: true });
      }
    }, 4500);

    return () => window.clearTimeout(safetyTimer);
  }, [clerk, navigate]);

  useEffect(() => {
    if (!clerk || !clerk.loaded || ranRef.current) return;
    ranRef.current = true;

    const base = (import.meta.env.BASE_URL || '/').replace(/\/$/, '');
    const pendingRole = readPendingClerkRole();
    const pendingMode = readPendingClerkAuthMode();
    const isSignInAttempt = pendingMode !== 'signup';
    const dest = pendingRole === 'artisan' ? '/auth?tab=verify' : '/login';
    const registerDest =
      pendingRole === 'artisan'
        ? '/auth?mode=register&not_registered=1'
        : '/register?not_registered=1';
    const fallbackAuthDest =
      pendingRole === 'artisan'
        ? `/auth?mode=${isSignInAttempt ? 'signin' : 'register'}`
        : isSignInAttempt
          ? '/login'
          : '/register';

    const go = (target) => {
      if (doneRef.current) return;
      doneRef.current = true;
      navigate(target, { replace: true });
    };

    Promise.resolve()
      .then(() =>
        clerk.handleRedirectCallback({
          transferable: !isSignInAttempt,
          signInUrl: `${base}${registerDest}`,
          signUpUrl: `${base}${registerDest}`,
          continueSignUpUrl: `${base}${registerDest}`,
          signInFallbackRedirectUrl: `${base}${dest}`,
          signUpFallbackRedirectUrl: `${base}${dest}`
        })
      )
      .then(() => {
        if (doneRef.current) return;
        const currentPath =
          (window.location.pathname || '/').replace(new RegExp(`^${base}`), '') || '/';
        if (currentPath !== '/sso-callback') {
          doneRef.current = true;
          return;
        }
        const siStatus = clerk.client?.signIn?.firstFactorVerification?.status;
        if (isSignInAttempt && (!clerk.user || siStatus === 'transferable' || siStatus === 'failed')) {
          clearPendingClerkRole();
          clearPendingClerkAuthMode();
          go(registerDest);
          return;
        }
        if (clerk.user) {
          go(dest);
          return;
        }
        clearPendingClerkRole();
        clearPendingClerkAuthMode();
        go(isSignInAttempt ? registerDest : fallbackAuthDest);
      })
      .catch(() => {
        if (doneRef.current) return;
        if (clerk.user) {
          go(dest);
          return;
        }
        clearPendingClerkRole();
        clearPendingClerkAuthMode();
        go(isSignInAttempt ? registerDest : fallbackAuthDest);
      });
  }, [clerk, clerk?.loaded, navigate]);

  return null;
}

function ClerkBridgeInner({ children }) {
  const navigate = useNavigate();
  const location = useLocation();
  const { isLoaded: userLoaded, isSignedIn, user: clerkUser } = useUser();
  const { isLoaded: authLoaded, getToken: clerkGetToken } = useAuth();
  const { session: clerkSession } = useSession();
  const clerk = useClerk();
  const { isLoaded: signInLoaded, signIn } = useSignIn();
  const { isLoaded: signUpLoaded, signUp } = useSignUp();
  const {
    user: storeUser,
    setUser,
    buyerProfile,
    setBuyerProfile,
    hydrateFromBackend,
    clearSessionState,
    toast
  } = useStore();

  const isLoaded = Boolean(userLoaded && authLoaded);
  const lastDbSyncKeyRef = useRef('');
  const syncedAccountIdsRef = useRef(new Set());
  const conflictSigningOutRef = useRef(false);
  const liveCheckInFlightRef = useRef(false);
  const lastLiveCheckAtRef = useRef(0);
  const resolvedRoleRef = useRef('buyer');

  const getCurrentAppPath = () => {
    const base = (import.meta.env.BASE_URL || '/').replace(/\/$/, '');
    return (window.location.pathname || '/').replace(new RegExp(`^${base}`), '') || '/';
  };

  const forceRevokedSignOut = useCallback(
    async ({ requestedRole = 'buyer', queryFlag = 'account_deleted=1', redirect = false, notice = '' } = {}) => {
      if (conflictSigningOutRef.current) return;
      conflictSigningOutRef.current = true;
      clearPendingClerkRole();
      clearPendingClerkAuthMode();
      lastDbSyncKeyRef.current = '';
      syncedAccountIdsRef.current.clear();
      clearSessionState();
      setUser(null, { silent: true });
      try {
        if (clerk?.signOut) {
          await clerk.signOut(() => {});
        }
      } catch {
        /* Clerk user/session may already be deleted server-side */
      }
      conflictSigningOutRef.current = false;

      if (notice && typeof toast === 'function') {
        toast(notice, 'info');
      }

      const currentPath = getCurrentAppPath();
      const onProtectedOrAuth = /^\/(profile|orders|seller|wholesale|auth|login|register)(\.html)?$/.test(
        currentPath
      );
      if (redirect || onProtectedOrAuth) {
        const registerDest =
          requestedRole === 'artisan'
            ? `/auth?mode=register&${queryFlag}`
            : `/register?${queryFlag}`;
        navigate(registerDest, { replace: true });
      }
    },
    [clerk, clearSessionState, navigate, setUser, toast]
  );

  const verifyLiveDbSession = useCallback(
    async ({ force = false, requestedRole = resolvedRoleRef.current } = {}) => {
      if (
        !canAttemptBackend() ||
        !isSignedIn ||
        !clerkUser?.id ||
        !clerkGetToken ||
        conflictSigningOutRef.current ||
        liveCheckInFlightRef.current
      ) {
        return;
      }
      const now = Date.now();
      if (!force && now - lastLiveCheckAtRef.current < 1500) {
        return;
      }
      liveCheckInFlightRef.current = true;
      lastLiveCheckAtRef.current = now;
      try {
        let token = null;
        try {
          token = await clerkGetToken({ skipCache: true });
        } catch (tokErr) {
          const clerkCode = tokErr?.errors?.[0]?.code || '';
          if (
            tokErr?.status === 401 ||
            tokErr?.status === 404 ||
            /session_not_found|resource_not_found|user_not_found|unauthenticated/i.test(clerkCode)
          ) {
            await forceRevokedSignOut({
              requestedRole,
              queryFlag: 'account_deleted=1',
              redirect: false,
              notice: 'Your HunarLink account session is no longer active.'
            });
            return;
          }
          token = await clerkGetToken().catch(() => null);
        }

        if (!token) {
          await forceRevokedSignOut({
            requestedRole,
            queryFlag: 'account_deleted=1',
            redirect: false,
            notice: 'Your HunarLink account session is no longer active.'
          });
          return;
        }

        const profile = await fetchMyAuthProfile(token);
        if (profile && profile.account_status && profile.account_status !== 'ACTIVE') {
          await forceRevokedSignOut({
            requestedRole,
            queryFlag: 'account_deleted=1',
            redirect: false,
            notice: 'Your HunarLink account has been deactivated.'
          });
        }
      } catch (err) {
        const isDeactivatedError =
          err?.status === 403 && /not active|DEACTIVATED|SUSPENDED/i.test(err?.message || '');
        if (err?.status === 401 || err?.status === 404 || isDeactivatedError) {
          await forceRevokedSignOut({
            requestedRole,
            queryFlag: 'account_deleted=1',
            redirect: false,
            notice: 'Your HunarLink account has been removed or deactivated.'
          });
        }
      } finally {
        liveCheckInFlightRef.current = false;
      }
    },
    [clerkGetToken, clerkUser?.id, forceRevokedSignOut, isSignedIn]
  );

  /* Sync the Clerk-authenticated user into HunarLink's FastAPI database
     (`users` + `user_role_assignments`) using a cryptographically verified
     Clerk RS256 session JWT, enforcing:
       1) Existing DB users/artisans attempting Register (`auth_mode='signup'`)
          get HTTP 409 Conflict -> immediately sign out & send to Sign In.
       2) Any artisan whose DB `verification_status !== 'APPROVED'` ALWAYS
          lands on `/auth?tab=verify` first (on signup, login, or /seller). */
  const syncUserToBackend = useCallback(
    async (clerkAccount, syncedMeta, requestedRole, authMode = 'sync') => {
      if (!canAttemptBackend() || !clerkAccount?.id || !clerkGetToken) return null;
      const syncKey = `${clerkAccount.id}:${requestedRole}:${authMode}`;
      if (lastDbSyncKeyRef.current === syncKey) {
        if (syncedAccountIdsRef.current.has(clerkAccount.id)) {
          await verifyLiveDbSession({ requestedRole });
        }
        return null;
      }
      const email = syncedMeta.email || '';
      if (!email) return null;

      try {
        let token = null;
        try {
          token = await clerkGetToken({ skipCache: true });
        } catch (tokErr) {
          const clerkCode = tokErr?.errors?.[0]?.code || '';
          if (
            tokErr?.status === 401 ||
            tokErr?.status === 404 ||
            /session_not_found|resource_not_found|user_not_found|unauthenticated/i.test(clerkCode)
          ) {
            await forceRevokedSignOut({
              requestedRole,
              queryFlag: 'account_deleted=1',
              redirect: true,
              notice: 'Your HunarLink account session is no longer active.'
            });
            return null;
          }
          token = await clerkGetToken().catch(() => null);
        }
        if (!token) {
          await forceRevokedSignOut({
            requestedRole,
            queryFlag: 'account_deleted=1',
            redirect: true,
            notice: 'Your HunarLink account session is no longer active.'
          });
          return null;
        }
        const emailVerified = Boolean(
          clerkAccount.primaryEmailAddress?.verification?.status === 'verified'
        );
        const effectiveAuthMode =
          authMode === 'signup' && syncedAccountIdsRef.current.has(clerkAccount.id)
            ? 'sync'
            : authMode === 'signup' || authMode === 'signin'
              ? authMode
              : 'sync';
        let dpdpMeta = {};
        try {
          const rawConsent = window.sessionStorage.getItem('hunarlink_pending_dpdp_consent');
          if (rawConsent) dpdpMeta = JSON.parse(rawConsent) || {};
        } catch {
          dpdpMeta = {};
        }
        const res = await syncAuthenticatedUser(
          {
            email,
            email_verified: emailVerified,
            first_name: syncedMeta.first || 'Collector',
            last_name: syncedMeta.last || null,
            display_name: syncedMeta.fullName || syncedMeta.first || null,
            phone: syncedMeta.phone || null,
            requested_role: requestedRole === 'artisan' ? 'artisan' : 'buyer',
            auth_mode: effectiveAuthMode,
            ...(typeof dpdpMeta.dpdpAccepted === 'boolean'
              ? { dpdp_consent_accepted: dpdpMeta.dpdpAccepted }
              : {}),
            ...(typeof dpdpMeta.age18 === 'boolean'
              ? { age_confirmed: dpdpMeta.age18 }
              : {}),
            ...(typeof dpdpMeta.marketingOptIn === 'boolean'
              ? { marketing_opt_in: dpdpMeta.marketingOptIn }
              : {})
          },
          token
        );
        try {
          window.sessionStorage.removeItem('hunarlink_pending_dpdp_consent');
        } catch {
          /* ignore */
        }
        lastDbSyncKeyRef.current = syncKey;
        syncedAccountIdsRef.current.add(clerkAccount.id);

        const dbIsArtisan = Boolean(res?.is_artisan) || requestedRole === 'artisan';
        const dbArtisanVerified = Boolean(res?.artisan_verified);
        const dbVerificationStatus =
          res?.seller_profile?.verification_status || 'UNVERIFIED';
        const effectiveRole = dbIsArtisan ? 'artisan' : 'buyer';
        saveUserRole(clerkAccount.id, effectiveRole);

        if (dbIsArtisan) {
          const existingLocal = readClerkArtisanProfile(clerkAccount.id) || {};
          const sp = res?.seller_profile || null;
          const mergedArtisan = {
            ...existingLocal,
            name: res?.display_name || syncedMeta.fullName || existingLocal.name || '',
            email: res?.email || syncedMeta.email || '',
            phone: res?.phone || syncedMeta.phone || existingLocal.phone || '',
            sellerProfileId: sp?.seller_profile_id || existingLocal.sellerProfileId || null,
            business: sp?.store_name || existingLocal.business || '',
            craft: sp?.craft_specialty || existingLocal.craft || '',
            district: sp?.workshop_district || existingLocal.district || '',
            giCertified: sp?.verification_path === 'GI' && dbArtisanVerified,
            giId: sp?.claimed_gi_authorized_user_no || existingLocal.giId || null,
            verificationPath: sp?.verification_path || existingLocal.verificationPath || null,
            verificationStatus: dbVerificationStatus,
            profileStatus: sp?.profile_status || 'DRAFT',
            applicationNumber: sp?.latest_application_number || existingLocal.applicationNumber || null,
            reviewDecisionNotes: sp?.review_decision_notes || null,
            artisanVerified: dbArtisanVerified,
            title: dbArtisanVerified
              ? 'Verified Artisan \u2022 HunarLink DB'
              : dbVerificationStatus === 'SUBMITTED'
                ? 'Artisan Verification Pending Review'
                : 'Artisan Verification Required'
          };
          saveClerkArtisanProfile(clerkAccount.id, mergedArtisan);
        }

        const refreshed = buildSyncedUser(clerkAccount, effectiveRole);
        setUser(
          {
            ...refreshed.payload,
            role: effectiveRole,
            artisanVerified: dbIsArtisan ? dbArtisanVerified : false,
            verificationStatus: dbVerificationStatus,
            sellerProfile: res?.seller_profile || null,
            sellerProfileId: res?.seller_profile?.seller_profile_id || null,
            applicationNumber: res?.seller_profile?.latest_application_number || null,
            reviewDecisionNotes: res?.seller_profile?.review_decision_notes || null,
            dbUserId: res?.user_id || null,
            dbRoles: res?.roles || [],
            isAdmin: Boolean(res?.is_admin)
          },
          { silent: true }
        );

        if (!dbIsArtisan) {
          setBuyerProfile({
            ...(buyerProfile || {}),
            firstName: syncedMeta.first,
            lastName: syncedMeta.last,
            fullName: syncedMeta.fullName,
            email: syncedMeta.email,
            phone: syncedMeta.phone || buyerProfile?.phone || '',
            avatarPhoto: clerkAccount.imageUrl || buyerProfile?.avatarPhoto || '',
            badge: syncedMeta.badge,
            role: 'buyer',
            isLoggedIn: true
          });
        }

        const currentPath = getCurrentAppPath();
        const isEntryOrAuth =
          currentPath === '/' ||
          currentPath === '/index.html' ||
          currentPath === '/login' ||
          currentPath === '/register' ||
          currentPath === '/sso-callback';
        const isSellerPath = currentPath === '/seller';

        if (dbIsArtisan && !dbArtisanVerified) {
          if (isEntryOrAuth || isSellerPath) {
            navigate('/auth?tab=verify', { replace: true });
          }
        } else if (dbIsArtisan && dbArtisanVerified) {
          if (currentPath === '/login' || currentPath === '/register' || currentPath === '/sso-callback') {
            navigate('/seller', { replace: true });
          }
        } else if (!dbIsArtisan && (currentPath === '/login' || currentPath === '/register' || currentPath === '/sso-callback')) {
          navigate('/', { replace: true });
        }
        if (import.meta.env.DEV) {
          console.info(
            `[HunarLink DB] ${res.is_new_user ? 'Created new' : 'Synced'} user ${res.email} (id=${res.user_id}, roles=${res.roles.join(',')}, artisan_verified=${dbArtisanVerified})`
          );
        }
        await hydrateFromBackend(token);
        return res;
      } catch (err) {
        const isDeactivatedError =
          err?.status === 403 &&
          /not active|DEACTIVATED/i.test(err?.message || '');
        if (err?.status === 403 && !isDeactivatedError) {
          conflictSigningOutRef.current = true;
          clearPendingClerkRole();
          clearPendingClerkAuthMode();
          lastDbSyncKeyRef.current = '';
          syncedAccountIdsRef.current.clear();
          clearSessionState();
          setUser(null, { silent: true });
          try {
            if (clerk?.signOut) {
              await clerk.signOut(() => {});
            }
          } catch {
            /* ignore */
          }
          conflictSigningOutRef.current = false;
          const msg = encodeURIComponent(
            err?.message || 'Role mismatch: this account belongs to a different HunarLink role.'
          );
          const roleQuery = requestedRole === 'artisan' ? '&role=artisan' : '';
          navigate(
            requestedRole === 'artisan'
              ? `/auth?mode=signin&role_conflict=1&conflict_msg=${msg}`
              : `/login?mode=signin&role_conflict=1${roleQuery}&conflict_msg=${msg}`,
            { replace: true }
          );
          return null;
        }
        if (err?.status === 404 || err?.status === 401 || isDeactivatedError) {
          // Strict DB login check: user does NOT exist (or was deleted/deactivated) ->
          // sign out Clerk immediately and redirect to Register page for the respective role!
          conflictSigningOutRef.current = true;
          clearPendingClerkRole();
          clearPendingClerkAuthMode();
          lastDbSyncKeyRef.current = '';
          syncedAccountIdsRef.current.clear();
          clearSessionState();
          setUser(null, { silent: true });
          try {
            if (clerk?.signOut) {
              await clerk.signOut(() => {});
            }
          } catch {
            /* ignore */
          }
          conflictSigningOutRef.current = false;
          const queryFlag = isDeactivatedError ? 'account_deleted=1' : 'not_registered=1';
          const registerDest =
            requestedRole === 'artisan'
              ? `/auth?mode=register&${queryFlag}`
              : `/register?${queryFlag}`;
          navigate(registerDest, { replace: true });
          return null;
        }
        if (err?.status === 409 && authMode === 'signup') {
          conflictSigningOutRef.current = true;
          clearPendingClerkRole();
          clearPendingClerkAuthMode();
          lastDbSyncKeyRef.current = '';
          syncedAccountIdsRef.current.clear();
          clearSessionState();
          setUser(null, { silent: true });
          try {
            if (clerk?.signOut) {
              await clerk.signOut(() => {});
            }
          } catch {
            /* ignore */
          }
          conflictSigningOutRef.current = false;
          const roleQuery = requestedRole === 'artisan' ? '&role=artisan' : '';
          navigate(`/login?mode=signin&already_registered=1${roleQuery}`, { replace: true });
          return null;
        }
        if (import.meta.env.DEV) {
          console.warn(
            `[HunarLink DB] Could not sync Clerk user to FastAPI (${err?.status || 'offline'}): ${err?.message || 'unknown error'}`
          );
        }
        return null;
      }
    },
    [buyerProfile, clerk, clerkGetToken, clearSessionState, forceRevokedSignOut, hydrateFromBackend, navigate, setBuyerProfile, setUser, verifyLiveDbSession]
  );

  /* Mirror the live Clerk user into StoreContext ONLY after verifying against
     HunarLink's database when the backend is active (prevents unregistered
     Google/Apple sign-ins from ever entering the app). */
  useEffect(() => {
    if (!isLoaded) return;

    if (!isSignedIn || !clerkUser) {
      lastDbSyncKeyRef.current = '';
      syncedAccountIdsRef.current.clear();
      clearSessionState();
      if (storeUser) {
        setUser(null, { silent: true });
      }
      return;
    }

    if (conflictSigningOutRef.current) return;

    // Wait for <AuthenticateWithRedirectCallback /> on /sso-callback to finish
    // navigating to /login or /auth before reading/clearing pendingAuthMode and
    // validating against MySQL DB so its redirect cannot overwrite our 404/409 bounces.
    if (getCurrentAppPath() === '/sso-callback') return;

    const pendingRole = readPendingClerkRole();
    const pendingAuthMode = readPendingClerkAuthMode();
    if (pendingRole) clearPendingClerkRole();
    if (pendingAuthMode) clearPendingClerkAuthMode();

    const roleMap = readRoleMap();
    const metaRole = clerkUser.publicMetadata?.role;
    const resolvedRole =
      pendingRole ||
      (metaRole === 'artisan' || metaRole === 'buyer' ? metaRole : null) ||
      roleMap[clerkUser.id] ||
      'buyer';

    resolvedRoleRef.current = resolvedRole;
    saveUserRole(clerkUser.id, resolvedRole);

    const synced = buildSyncedUser(clerkUser, resolvedRole);
    const effectiveAuthMode =
      pendingAuthMode === 'signup'
        ? 'signup'
        : syncedAccountIdsRef.current.has(clerkUser.id)
          ? 'sync'
          : 'signin';

    if (canAttemptBackend()) {
      // Wait for FastAPI DB verification (200 OK) before marking user logged in.
      syncUserToBackend(clerkUser, synced, resolvedRole, effectiveAuthMode);
      return;
    }

    // Static preview fallback when backend is offline
    setUser(synced.payload, { silent: true });
    if (resolvedRole === 'buyer') {
      setBuyerProfile({
        ...(buyerProfile || {}),
        firstName: synced.first,
        lastName: synced.last,
        fullName: synced.fullName,
        email: synced.email,
        phone: synced.phone || buyerProfile?.phone || '',
        avatarPhoto: clerkUser.imageUrl || buyerProfile?.avatarPhoto || '',
        badge: synced.badge,
        role: 'buyer',
        isLoggedIn: true
      });
    } else if (resolvedRole === 'artisan' && !synced.artisanVerified) {
      const currentPath = getCurrentAppPath();
      if (
        currentPath === '/' ||
        currentPath === '/index.html' ||
        currentPath === '/login' ||
        currentPath === '/register' ||
        currentPath === '/sso-callback' ||
        currentPath === '/seller'
      ) {
        navigate('/auth?tab=verify', { replace: true });
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isLoaded, isSignedIn, clerkUser?.id, clerkUser?.updatedAt, location.pathname]);

  /* Continuous session enforcement:
     If an Admin deletes/deactivates this account in another tab (or via CLI / DB),
     immediately sign the user out of this tab via:
       1) Global API 401/403 revocation hook,
       2) Cross-tab BroadcastChannel + localStorage revocation signal,
       3) Window focus / tab visibility DB re-check (/api/v1/auth/me), and
       4) Periodic 15s background verification while the tab stays visible. */
  useEffect(() => {
    if (!isLoaded || !isSignedIn || !clerkUser?.id || !canAttemptBackend()) {
      setAuthRevokedHandler(null);
      return;
    }

    const currentEmail = (
      clerkUser.primaryEmailAddress?.emailAddress ||
      storeUser?.email ||
      ''
    )
      .trim()
      .toLowerCase();
    const currentDbId = storeUser?.dbUserId || null;

    const handleRevocationPayload = (payload) => {
      if (!payload || payload.type !== 'USER_DELETED') return;
      const matchesUser =
        (payload.userId && currentDbId && payload.userId === currentDbId) ||
        (payload.clerkUserId && payload.clerkUserId === clerkUser.id) ||
        (payload.email && currentEmail && payload.email === currentEmail);
      if (matchesUser) {
        forceRevokedSignOut({
          requestedRole: resolvedRoleRef.current,
          queryFlag: 'account_deleted=1',
          redirect: false,
          notice: 'Your HunarLink account has been removed by an administrator.'
        });
      } else {
        verifyLiveDbSession({ force: true });
      }
    };

    setAuthRevokedHandler(() => {
      forceRevokedSignOut({
        requestedRole: resolvedRoleRef.current,
        queryFlag: 'account_deleted=1',
        redirect: false,
        notice: 'Your HunarLink account session is no longer active.'
      });
    });

    const onFocusOrVisible = () => {
      if (document.visibilityState === 'hidden') return;
      verifyLiveDbSession();
    };
    window.addEventListener('focus', onFocusOrVisible);
    document.addEventListener('visibilitychange', onFocusOrVisible);

    const onStorage = (e) => {
      if (e.key !== SESSION_REVOKED_STORAGE_KEY || !e.newValue) return;
      try {
        handleRevocationPayload(JSON.parse(e.newValue));
      } catch {
        verifyLiveDbSession({ force: true });
      }
    };
    window.addEventListener('storage', onStorage);

    let channel = null;
    try {
      if (typeof BroadcastChannel !== 'undefined') {
        channel = new BroadcastChannel(SESSION_EVENTS_CHANNEL);
        channel.onmessage = (evt) => handleRevocationPayload(evt?.data);
      }
    } catch {
      channel = null;
    }

    const timer = window.setInterval(() => {
      if (document.visibilityState !== 'hidden') {
        verifyLiveDbSession();
      }
    }, 15000);

    return () => {
      setAuthRevokedHandler(null);
      window.removeEventListener('focus', onFocusOrVisible);
      document.removeEventListener('visibilitychange', onFocusOrVisible);
      window.removeEventListener('storage', onStorage);
      if (channel) {
        try {
          channel.close();
        } catch {
          /* ignore */
        }
      }
      window.clearInterval(timer);
    };
  }, [
    clerkUser?.id,
    clerkUser?.primaryEmailAddress?.emailAddress,
    forceRevokedSignOut,
    isLoaded,
    isSignedIn,
    storeUser?.dbUserId,
    storeUser?.email,
    verifyLiveDbSession
  ]);

  const authenticateWithOAuth = useCallback(
    async (provider, { role = 'user', mode = 'signin', redirectTo = '/' } = {}) => {
      const normalizedRole = role === 'artisan' ? 'artisan' : 'buyer';
      const base = (import.meta.env.BASE_URL || '/').replace(/\/$/, '');

      /* If already signed in via Clerk, verify role against DB before switching workspace */
      if (isSignedIn && clerkUser) {
        const synced = buildSyncedUser(clerkUser, normalizedRole);
        if (canAttemptBackend()) {
          const res = await syncUserToBackend(clerkUser, synced, normalizedRole, 'signin');
          if (!res) {
            return { alreadySignedIn: false };
          }
        } else {
          saveUserRole(clerkUser.id, normalizedRole);
          setUser(synced.payload, { silent: true });
        }

        if (normalizedRole === 'buyer') {
          setBuyerProfile({
            ...(buyerProfile || {}),
            firstName: synced.first,
            lastName: synced.last,
            fullName: synced.fullName,
            email: synced.email,
            phone: synced.phone || buyerProfile?.phone || '',
            avatarPhoto: clerkUser.imageUrl || buyerProfile?.avatarPhoto || '',
            badge: synced.badge,
            role: 'buyer',
            isLoggedIn: true
          });
          const buyerDest = sanitizeInternalRedirect(redirectTo, '/');
          return { alreadySignedIn: true, destination: buyerDest, artisanVerified: false };
        }

        const artisanDest = synced.artisanVerified
          ? '/seller'
          : '/auth?mode=register&step=verify';
        return {
          alreadySignedIn: true,
          destination: artisanDest,
          artisanVerified: synced.artisanVerified
        };
      }

      const useSignUpFlow = mode === 'signup' || mode === 'register';
      const normalizedAuthMode = useSignUpFlow ? 'signup' : 'signin';
      const ready = useSignUpFlow ? signUpLoaded && signUp : signInLoaded && signIn;
      if (!ready) {
        throw new Error('Clerk is still initialising. Please try again in a moment.');
      }

      const strategy =
        String(provider || '').toLowerCase() === 'apple' ? 'oauth_apple' : 'oauth_google';
      const origin = window.location.origin;
      // Always route OAuth callback through /login (buyer) or /auth?tab=verify (artisan)
      // so ClerkBoundary validates registration against MySQL DB BEFORE entering / or /seller.
      const destPath = normalizedRole === 'artisan' ? '/auth?tab=verify' : '/login';
      const redirectUrl = `${origin}${base}/sso-callback`;
      const redirectUrlComplete = `${origin}${base}${destPath}`;

      setPendingClerkRole(normalizedRole);
      setPendingClerkAuthMode(normalizedAuthMode);

      const resource = useSignUpFlow ? signUp : signIn;
      const timeoutPromise = new Promise((_, reject) => {
        window.setTimeout(() => {
          reject(
            new Error(
              `Clerk did not start the ${provider} redirect in time. Check that ${provider} is enabled in your Clerk Dashboard and allowed for ${origin}.`
            )
          );
        }, 12000);
      });

      try {
        await Promise.race([
          resource.authenticateWithRedirect({
            strategy,
            redirectUrl,
            redirectUrlComplete
          }),
          timeoutPromise
        ]);
        return { redirected: true };
      } catch (err) {
        clearPendingClerkRole();
        clearPendingClerkAuthMode();
        throw new Error(formatClerkError(err, provider));
      }
    },
    [buyerProfile, clerkUser, isSignedIn, setBuyerProfile, setUser, signIn, signInLoaded, signUp, signUpLoaded, syncUserToBackend]
  );

  const signOutClerk = useCallback(async () => {
    clearPendingClerkRole();
    clearPendingClerkAuthMode();
    lastDbSyncKeyRef.current = '';
    clearSessionState();
    setUser(null, { silent: true });
    if (isSignedIn && clerk?.signOut) {
      await clerk.signOut(() => {});
    }
  }, [clerk, clearSessionState, isSignedIn, setUser]);

  const renderSsoCallback = useCallback(() => <SsoCallbackRunner />, []);

  const getToken = useCallback(async () => {
    if (!isSignedIn || typeof clerkGetToken !== 'function') return null;
    try {
      return (await clerkGetToken()) || null;
    } catch {
      return null;
    }
  }, [isSignedIn, clerkGetToken]);

  const sendEmailCode = useCallback(
    async (emailAddress, role = 'buyer', authMode = 'signin', password = '') => {
      const cleaned = String(emailAddress || '').trim().toLowerCase();
      if (!cleaned || !cleaned.includes('@')) {
        throw new Error('Please enter a valid email address.');
      }
      const trimmedPassword = String(password || '');
      const normalizedRole = role === 'artisan' ? 'artisan' : 'buyer';
      const normalizedMode = authMode === 'register' || authMode === 'signup' ? 'signup' : 'signin';
      if (normalizedMode === 'signup' && trimmedPassword) {
        const pwCheck = evaluatePassword(trimmedPassword);
        if (!pwCheck.isValid) {
          throw new Error(pwCheck.errorMessage);
        }
      }
      setPendingClerkRole(normalizedRole);
      setPendingClerkAuthMode(normalizedMode);

      if (!signInLoaded || !signUpLoaded || !signIn || !signUp) {
        throw new Error('Authentication service is initializing. Please retry.');
      }

      // 1. Live HunarLink DB check BEFORE calling Clerk:
      //    - Existing DB user/artisan CANNOT register (must log in).
      //    - Non-existent user on Sign In is directed cleanly to Register.
      //    - Strict role isolation blocks cross-role sign-in/signup (Buyer vs Artisan vs Admin).
      if (canAttemptBackend()) {
        try {
          const acct = await checkAuthAccount(cleaned, normalizedRole);
          if (acct?.role_conflict) {
            const roleErr = new Error(
              acct.conflict_message ||
                'This email is registered under a different role in HunarLink.'
            );
            roleErr.code = 'ROLE_CONFLICT';
            throw roleErr;
          }
          if (normalizedMode === 'signup' && acct?.exists) {
            const dupErr = new Error(
              'This email already exists in HunarLink. You cannot register again — please Sign In instead.'
            );
            dupErr.code = 'ALREADY_REGISTERED';
            throw dupErr;
          }
          if (normalizedMode === 'signin' && acct && acct.exists === false) {
            const missErr = new Error(
              'No HunarLink account exists for this email yet. Please switch to Register to create one.'
            );
            missErr.code = 'NOT_REGISTERED';
            throw missErr;
          }
        } catch (checkErr) {
          if (
            checkErr?.code === 'ALREADY_REGISTERED' ||
            checkErr?.code === 'NOT_REGISTERED' ||
            checkErr?.code === 'ROLE_CONFLICT'
          ) {
            clearPendingClerkRole();
            clearPendingClerkAuthMode();
            throw checkErr;
          }
          // Backend unreachable (static preview): proceed to Clerk
        }
      }

      if (normalizedMode === 'signup') {
        try {
          const createParams = { emailAddress: cleaned };
          if (trimmedPassword) {
            createParams.password = trimmedPassword;
          }
          const su = await signUp.create(createParams);
          if (su?.status === 'complete' && su?.createdSessionId) {
            await clerk.setActive({ session: su.createdSessionId });
            return { flow: 'complete' };
          }
          await signUp.prepareEmailAddressVerification({ strategy: 'email_code' });
          return { flow: 'signUp' };
        } catch (err) {
          clearPendingClerkRole();
          clearPendingClerkAuthMode();
          const errCode = err?.errors?.[0]?.code || '';
          const msg = err?.errors?.[0]?.longMessage || err?.errors?.[0]?.message || err?.message || '';
          if (errCode === 'form_identifier_exists' || msg.toLowerCase().includes('already')) {
            const dupErr = new Error(
              'This email already exists. You cannot register again — please Sign In instead.'
            );
            dupErr.code = 'ALREADY_REGISTERED';
            throw dupErr;
          }
          throw new Error(msg || 'Could not send registration verification code.');
        }
      }

      // Sign-In mode: NEVER silently fall back to signUp.create
      try {
        const si = await signIn.create({ identifier: cleaned });
        const emailFactor = si.supportedFirstFactors?.find((f) => f.strategy === 'email_code');
        if (!emailFactor) {
          throw new Error('Use "Sign in with Google" or "Sign in with Apple" for this account.');
        }
        await signIn.prepareFirstFactor({
          strategy: 'email_code',
          emailAddressId: emailFactor.emailAddressId
        });
        return { flow: 'signIn' };
      } catch (err) {
        clearPendingClerkRole();
        clearPendingClerkAuthMode();
        const errCode = err?.errors?.[0]?.code || '';
        const msg = err?.errors?.[0]?.longMessage || err?.errors?.[0]?.message || err?.message || '';
        if (errCode === 'form_identifier_not_found' || msg.toLowerCase().includes("couldn't find")) {
          const missErr = new Error(
            'No account found for this email yet. Please switch to Register to create one.'
          );
          missErr.code = 'NOT_REGISTERED';
          throw missErr;
        }
        throw new Error(msg || 'Could not send sign-in verification code.');
      }
    },
    [clerk, signIn, signInLoaded, signUp, signUpLoaded]
  );

  const verifyEmailCode = useCallback(
    async (code, flow = 'signIn', password = '') => {
      if (isSignedIn && clerkUser) {
        return true;
      }
      const cleaned = String(code || '').trim();
      const trimmedPassword = String(password || '');
      if (flow === 'signIn') {
        if (signIn?.status === 'complete' && signIn?.createdSessionId) {
          await clerk.setActive({ session: signIn.createdSessionId });
          return true;
        }
        try {
          const res =
            signIn?.status === 'needs_second_factor' && typeof signIn.attemptSecondFactor === 'function'
              ? await signIn.attemptSecondFactor({ strategy: 'email_code', code: cleaned })
              : await signIn.attemptFirstFactor({ strategy: 'email_code', code: cleaned });
          if (res.status === 'complete' && res.createdSessionId) {
            await clerk.setActive({ session: res.createdSessionId });
            return true;
          }
        } catch (err) {
          const msg = err?.errors?.[0]?.longMessage || err?.errors?.[0]?.message || err?.message || '';
          if (msg.toLowerCase().includes('already') && signIn?.createdSessionId) {
            await clerk.setActive({ session: signIn.createdSessionId });
            return true;
          }
          throw new Error(msg || 'Invalid or expired verification code.');
        }
      } else {
        const finalizeSignUp = async (suResource) => {
          let current = suResource || signUp;
          if (!current) return false;
          if (current.status === 'complete' && current.createdSessionId) {
            await clerk.setActive({ session: current.createdSessionId });
            return true;
          }
          if (current.status === 'missing_requirements') {
            const missing = Array.isArray(current.missingFields) ? current.missingFields : [];
            const emailStr =
              current.emailAddress ||
              current.verifications?.emailAddress?.nextAction ||
              'artisan';
            const localPrefix =
              String(emailStr)
                .split('@')[0]
                .replace(/[^a-zA-Z0-9_]/g, '')
                .slice(0, 20) || 'hunarlink';
            const patch = {};
            if (missing.includes('first_name')) patch.firstName = localPrefix;
            if (missing.includes('last_name')) patch.lastName = 'Member';
            if (missing.includes('username')) {
              patch.username = `${localPrefix}_${Math.floor(1000 + Math.random() * 9000)}`;
            }
            if (missing.includes('password')) {
              const randTail = `${Math.random().toString(36).slice(2, 10)}${Math.random().toString(36).slice(2, 10)}`;
              patch.password = evaluatePassword(trimmedPassword).isValid
                ? trimmedPassword
                : `Hl!Kmr#${randTail.slice(0, 12)}9A@2026`;
            }
            if (missing.includes('legal_accepted')) {
              patch.legalAccepted = true;
            }
            if (Object.keys(patch).length > 0 && typeof current.update === 'function') {
              current = await current.update(patch);
              if (current.status === 'complete' && current.createdSessionId) {
                await clerk.setActive({ session: current.createdSessionId });
                return true;
              }
            }
          }
          return false;
        };

        if (signUp?.verifications?.emailAddress?.status === 'verified') {
          if (await finalizeSignUp(signUp)) return true;
        }

        try {
          const res = await signUp.attemptEmailAddressVerification({ code: cleaned });
          if (await finalizeSignUp(res)) return true;
        } catch (err) {
          const errCode = err?.errors?.[0]?.code || '';
          const msg = err?.errors?.[0]?.longMessage || err?.errors?.[0]?.message || err?.message || '';
          if (
            errCode === 'verification_already_verified' ||
            msg.toLowerCase().includes('already been verified')
          ) {
            if (await finalizeSignUp(signUp)) return true;
            if (isSignedIn) return true;
            const switchErr = new Error(
              'Email verified. Please enter a fresh Sign-In code below to continue.'
            );
            switchErr.code = 'SWITCH_TO_SIGNIN';
            throw switchErr;
          }
          throw new Error(msg || 'Invalid or expired verification code.');
        }
      }
      throw new Error('Verification incomplete. Please request a fresh code.');
    },
    [clerk, clerkUser, isSignedIn, signIn, signUp]
  );

  const signInWithPassword = useCallback(
    async (emailAddress, password, role = 'buyer') => {
      const cleaned = String(emailAddress || '').trim().toLowerCase();
      if (!cleaned || !cleaned.includes('@')) {
        throw new Error('Please enter a valid email address.');
      }
      if (!password) {
        throw new Error('Please enter your password.');
      }
      const normalizedRole = role === 'artisan' ? 'artisan' : 'buyer';
      setPendingClerkRole(normalizedRole);
      setPendingClerkAuthMode('signin');

      if (!signInLoaded || !signIn) {
        throw new Error('Authentication service is initializing. Please retry.');
      }

      if (canAttemptBackend()) {
        try {
          const acct = await checkAuthAccount(cleaned, normalizedRole);
          if (acct?.role_conflict) {
            const roleErr = new Error(
              acct.conflict_message ||
                'This email is registered under a different role in HunarLink.'
            );
            roleErr.code = 'ROLE_CONFLICT';
            throw roleErr;
          }
          if (acct && acct.exists === false) {
            const missErr = new Error(
              'No HunarLink account exists for this email yet. Please switch to Register to create one.'
            );
            missErr.code = 'NOT_REGISTERED';
            throw missErr;
          }
        } catch (checkErr) {
          if (checkErr?.code === 'NOT_REGISTERED' || checkErr?.code === 'ROLE_CONFLICT') {
            clearPendingClerkRole();
            clearPendingClerkAuthMode();
            throw checkErr;
          }
        }
      }

      try {
        const res = await signIn.create({
          identifier: cleaned,
          password: String(password)
        });
        if (res.status === 'complete' && res.createdSessionId) {
          await clerk.setActive({ session: res.createdSessionId });
          return { status: 'complete' };
        }
        if (res.status === 'needs_second_factor') {
          const emailSecond = res.supportedSecondFactors?.find((f) => f.strategy === 'email_code');
          if (emailSecond) {
            await signIn.prepareSecondFactor({
              strategy: 'email_code',
              emailAddressId: emailSecond.emailAddressId
            });
            return { status: 'needs_second_factor', strategy: 'email_code' };
          }
        }
        const emailFirst = res.supportedFirstFactors?.find((f) => f.strategy === 'email_code');
        if (res.status === 'needs_first_factor' && emailFirst) {
          await signIn.prepareFirstFactor({
            strategy: 'email_code',
            emailAddressId: emailFirst.emailAddressId
          });
          return { status: 'needs_email_code' };
        }
        throw new Error(
          'Password sign-in could not complete for this account. Try "Send Sign-In Code" or Google.'
        );
      } catch (err) {
        clearPendingClerkRole();
        clearPendingClerkAuthMode();
        const errCode = err?.errors?.[0]?.code || '';
        const msg = err?.errors?.[0]?.longMessage || err?.errors?.[0]?.message || err?.message || '';
        if (errCode === 'form_identifier_not_found' || msg.toLowerCase().includes("couldn't find")) {
          const missErr = new Error(
            'No account found for this email yet. Please switch to Register to create one.'
          );
          missErr.code = 'NOT_REGISTERED';
          throw missErr;
        }
        throw new Error(msg || 'Invalid email or password.');
      }
    },
    [clerk, signIn, signInLoaded]
  );

  const sendPasswordResetCode = useCallback(
    async (emailAddress, role = 'buyer') => {
      const cleaned = String(emailAddress || '').trim().toLowerCase();
      if (!cleaned || !cleaned.includes('@')) {
        throw new Error('Please enter a valid email address.');
      }
      const normalizedRole = role === 'artisan' ? 'artisan' : 'buyer';
      setPendingClerkRole(normalizedRole);
      setPendingClerkAuthMode('signin');

      if (!signInLoaded || !signIn) {
        throw new Error('Authentication service is initializing. Please retry.');
      }

      if (canAttemptBackend()) {
        try {
          const acct = await checkAuthAccount(cleaned, normalizedRole);
          if (acct?.role_conflict) {
            const roleErr = new Error(
              acct.conflict_message ||
                'This email is registered under a different role in HunarLink.'
            );
            roleErr.code = 'ROLE_CONFLICT';
            throw roleErr;
          }
          if (acct && acct.exists === false) {
            const missErr = new Error(
              'No HunarLink account exists for this email yet. Please switch to Register to create one.'
            );
            missErr.code = 'NOT_REGISTERED';
            throw missErr;
          }
        } catch (checkErr) {
          if (checkErr?.code === 'NOT_REGISTERED' || checkErr?.code === 'ROLE_CONFLICT') {
            clearPendingClerkRole();
            clearPendingClerkAuthMode();
            throw checkErr;
          }
        }
      }

      try {
        const si = await signIn.create({
          strategy: 'reset_password_email_code',
          identifier: cleaned
        });
        // If Clerk returned needs_first_factor without preparing verification yet, prepare it explicitly
        if (
          si?.status === 'needs_first_factor' &&
          si?.firstFactorVerification?.status !== 'unverified'
        ) {
          const resetFactor = si.supportedFirstFactors?.find(
            (f) => f.strategy === 'reset_password_email_code'
          );
          if (!resetFactor) {
            throw new Error(
              'Password reset is not available for this account (it may use Google or Apple login). Try "Sign in with 6-digit email code instead" or Google.'
            );
          }
          await signIn.prepareFirstFactor({
            strategy: 'reset_password_email_code',
            emailAddressId: resetFactor.emailAddressId
          });
        }
        return { sent: true, email: cleaned };
      } catch (err) {
        clearPendingClerkRole();
        clearPendingClerkAuthMode();
        const errCode = err?.errors?.[0]?.code || '';
        const msg = err?.errors?.[0]?.longMessage || err?.errors?.[0]?.message || err?.message || '';
        if (errCode === 'form_identifier_not_found' || msg.toLowerCase().includes("couldn't find")) {
          const missErr = new Error(
            'No account found for this email yet. Please switch to Register to create one.'
          );
          missErr.code = 'NOT_REGISTERED';
          throw missErr;
        }
        throw new Error(msg || 'Could not send password reset code.');
      }
    },
    [signIn, signInLoaded]
  );

  const completePasswordReset = useCallback(
    async (code, newPassword) => {
      const cleanedCode = String(code || '').trim();
      const pwd = String(newPassword || '');
      if (!cleanedCode) {
        throw new Error('Please enter the 6-digit reset code sent to your email.');
      }
      const pwCheck = evaluatePassword(pwd);
      if (!pwCheck.isValid) {
        throw new Error(pwCheck.errorMessage);
      }
      if (!signInLoaded || !signIn) {
        throw new Error('Authentication service is initializing. Please retry.');
      }

      try {
        let res = await signIn.attemptFirstFactor({
          strategy: 'reset_password_email_code',
          code: cleanedCode,
          password: pwd
        });
        if (res.status === 'needs_new_password') {
          res = await signIn.resetPassword({
            password: pwd,
            signOutOfOtherSessions: true
          });
        }
        if (res.status === 'complete' && res.createdSessionId) {
          await clerk.setActive({ session: res.createdSessionId });
          return { status: 'complete' };
        }
        if (res.status === 'needs_second_factor') {
          const emailSecond = res.supportedSecondFactors?.find((f) => f.strategy === 'email_code');
          if (emailSecond) {
            await signIn.prepareSecondFactor({
              strategy: 'email_code',
              emailAddressId: emailSecond.emailAddressId
            });
            return { status: 'needs_second_factor' };
          }
          throw new Error('Additional verification is required after password reset.');
        }
        throw new Error('Could not complete password reset. Request a fresh reset code and try again.');
      } catch (err) {
        const msg = err?.errors?.[0]?.longMessage || err?.errors?.[0]?.message || err?.message || '';
        throw new Error(msg || 'Invalid or expired reset code, or password did not meet Clerk policy.');
      }
    },
    [clerk, signIn, signInLoaded]
  );

  const sendDeleteVerificationCode = useCallback(async () => {
    const activeSession = clerkSession || clerk?.session;
    if (!isSignedIn || !clerkUser || !activeSession) {
      throw new Error('You must be signed in to verify account deletion.');
    }
    const sv = await activeSession.startVerification({ level: 'first_factor' });
    const emailFactor = sv?.supportedFirstFactors?.find((f) => f.strategy === 'email_code');
    if (!emailFactor?.emailAddressId) {
      throw new Error('Email verification is not available on this session.');
    }
    await activeSession.prepareFirstFactorVerification({
      strategy: 'email_code',
      emailAddressId: emailFactor.emailAddressId
    });
    return {
      sent: true,
      email: clerkUser.primaryEmailAddress?.emailAddress || ''
    };
  }, [clerk?.session, clerkSession, clerkUser, isSignedIn]);

  const deleteMyAccount = useCallback(
    async ({ currentPassword = '', emailCode = '', reason = '' } = {}) => {
      const activeSession = clerkSession || clerk?.session;
      if (!isSignedIn || !clerkUser || !activeSession) {
        throw new Error('You must be signed in to delete your account.');
      }

      const hasPassword = Boolean(clerkUser.passwordEnabled);
      if (hasPassword) {
        const pwd = String(currentPassword || '');
        if (!pwd) {
          throw new Error('Please enter your current password to confirm account deletion.');
        }
        try {
          await activeSession.startVerification({ level: 'first_factor' });
          const verRes = await activeSession.attemptFirstFactorVerification({
            strategy: 'password',
            password: pwd
          });
          if (verRes?.status !== 'complete') {
            throw new Error(
              'Additional verification is required before deleting this account.'
            );
          }
        } catch (err) {
          const errCode = err?.errors?.[0]?.code || '';
          const msg =
            err?.errors?.[0]?.longMessage ||
            err?.errors?.[0]?.message ||
            err?.message ||
            '';
          if (
            errCode === 'form_password_incorrect' ||
            /incorrect|invalid/i.test(msg)
          ) {
            throw new Error('Incorrect current password. Your account was not deleted.');
          }
          throw new Error(msg || 'Could not verify your current password.');
        }
      } else {
        const cleanedCode = String(emailCode || '').replace(/\s+/g, '');
        if (!cleanedCode) {
          throw new Error(
            'Enter the 6-digit verification code sent to your email to confirm deletion.'
          );
        }
        try {
          const verRes = await activeSession.attemptFirstFactorVerification({
            strategy: 'email_code',
            code: cleanedCode
          });
          if (verRes?.status !== 'complete') {
            throw new Error('Verification code was incomplete. Please request a fresh code.');
          }
        } catch (err) {
          const msg =
            err?.errors?.[0]?.longMessage ||
            err?.errors?.[0]?.message ||
            err?.message ||
            '';
          throw new Error(msg || 'Invalid or expired verification code.');
        }
      }

      // Refresh JWT after reverification, then delete/anonymize in HunarLink DB FIRST
      // (so active orders block deletion before touching the Clerk account).
      let apiRes = { deleted: true, clerk_deleted: false };
      if (canAttemptBackend()) {
        const token = await clerkGetToken({ skipCache: true });
        if (!token) {
          throw new Error('Session token expired. Please sign in again and retry.');
        }
        apiRes = await deleteMyAccountApi(token, {
          currentPassword: hasPassword ? String(currentPassword || '') : null,
          reason: reason ? String(reason).trim() : null
        });
      }

      // Delete identity from Clerk Cloud after DB succeeds
      conflictSigningOutRef.current = true;
      try {
        if (!apiRes?.clerk_deleted && typeof clerkUser.delete === 'function') {
          try {
            await clerkUser.delete();
          } catch (clerkDelErr) {
            if (import.meta.env.DEV) {
              console.warn(
                '[HunarLink Auth] DB account deleted, but Clerk client self-delete threw:',
                clerkDelErr?.message || clerkDelErr
              );
            }
          }
        }
      } finally {
        clearPendingClerkRole();
        clearPendingClerkAuthMode();
        lastDbSyncKeyRef.current = '';
        syncedAccountIdsRef.current.clear();
        clearSessionState();
        setUser(null, { silent: true });
        try {
          if (clerk?.signOut) {
            await clerk.signOut(() => {});
          }
        } catch {
          /* ignore */
        }
        conflictSigningOutRef.current = false;
      }
      return apiRes;
    },
    [
      clerk,
      clerkGetToken,
      clerkSession,
      clerkUser,
      clearSessionState,
      isSignedIn,
      setUser
    ]
  );

  const bridgeValue = useMemo(
    () => ({
      enabled: true,
      isLoaded,
      isSignedIn: Boolean(isSignedIn),
      clerkUser: clerkUser || null,
      getToken,
      authenticateWithOAuth,
      sendEmailCode,
      verifyEmailCode,
      signInWithPassword,
      sendPasswordResetCode,
      completePasswordReset,
      signOutClerk,
      sendDeleteVerificationCode,
      deleteMyAccount,
      renderSsoCallback
    }),
    [
      isLoaded,
      isSignedIn,
      clerkUser,
      getToken,
      authenticateWithOAuth,
      sendEmailCode,
      verifyEmailCode,
      signInWithPassword,
      sendPasswordResetCode,
      completePasswordReset,
      signOutClerk,
      sendDeleteVerificationCode,
      deleteMyAccount,
      renderSsoCallback
    ]
  );

  return (
    <ClerkBridgeContext.Provider value={bridgeValue}>
      {children}
    </ClerkBridgeContext.Provider>
  );
}

function toRouterPath(to) {
  if (!to) return '/';
  try {
    const u = new URL(to, window.location.origin);
    if (u.origin !== window.location.origin) {
      // Never dump HunarLink users onto Clerk's hosted Account Portal
      // (e.g. *.accounts.dev/sign-up/tasks/choose-organization). Keep them in-app!
      if (
        u.hostname.endsWith('.accounts.dev') &&
        (u.pathname.includes('/tasks/') ||
          u.pathname.startsWith('/sign-up') ||
          u.pathname.startsWith('/sign-in'))
      ) {
        const pendingRole = readPendingClerkRole();
        const pendingMode = readPendingClerkAuthMode();
        if (pendingMode !== 'signup') {
          return pendingRole === 'artisan'
            ? '/auth?mode=register&not_registered=1'
            : '/register?not_registered=1';
        }
        return pendingRole === 'artisan' ? '/auth?tab=verify' : '/login';
      }
      window.location.assign(to);
      return null;
    }
    const base = (import.meta.env.BASE_URL || '/').replace(/\/$/, '');
    let p = u.pathname;
    if (base && p.startsWith(base)) p = p.slice(base.length) || '/';
    return `${p}${u.search}${u.hash}`;
  } catch {
    return to;
  }
}

export default function ClerkBoundary({ children }) {
  const navigate = useNavigate();
  const base = import.meta.env.BASE_URL || '/';
  const cleanBase = base.replace(/\/$/, '');

  const routerPush = useCallback(
    (to) => {
      const target = toRouterPath(to);
      if (target) navigate(target);
    },
    [navigate]
  );

  const routerReplace = useCallback(
    (to) => {
      const target = toRouterPath(to);
      if (target) navigate(target, { replace: true });
    },
    [navigate]
  );

  return (
    <ClerkProvider
      publishableKey={CLERK_PUBLISHABLE_KEY}
      signInUrl={`${cleanBase}/login`}
      signUpUrl={`${cleanBase}/register`}
      taskUrls={{
        'choose-organization': `${cleanBase}/login`
      }}
      afterSignOutUrl={base}
      routerPush={routerPush}
      routerReplace={routerReplace}
    >
      <ClerkBridgeInner>{children}</ClerkBridgeInner>
    </ClerkProvider>
  );
}
