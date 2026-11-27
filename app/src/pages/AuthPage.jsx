import React, { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { useStore } from '../state/StoreContext.jsx';
import {
  clearPendingClerkAuthMode,
  clearPendingClerkRole,
  readClerkArtisanProfile,
  saveClerkArtisanProfile,
  useClerkBridge
} from '../data/clerkConfig.js';
import {
  canAttemptBackend,
  fetchMyAuthProfile,
  submitArtisanVerification,
  syncAuthenticatedUser,
  uploadGuardrailDocument
} from '../services/apiClient.js';
import { IconArrowRight, IconBadgeCheck, IconCheck, IconShield, IconSpark } from '../components/LineIcons.jsx';
import { hdSrcFor, srcSetFor } from '../data/imageVariants.js';
import '../styles/portal.css';

function GoogleGlyph() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true">
      <path fill="#4285F4" d="M23.49 12.27c0-.79-.07-1.55-.2-2.27H12v4.3h6.45a5.52 5.52 0 0 1-2.39 3.62v3h3.87c2.26-2.08 3.56-5.15 3.56-8.65z" />
      <path fill="#34A853" d="M12 24c3.24 0 5.95-1.07 7.93-2.91l-3.87-3c-1.07.72-2.44 1.14-4.06 1.14-3.12 0-5.77-2.11-6.71-4.95H1.29v3.1A12 12 0 0 0 12 24z" />
      <path fill="#FBBC05" d="M5.29 14.28A7.2 7.2 0 0 1 4.91 12c0-.79.14-1.56.38-2.28v-3.1H1.29A12 12 0 0 0 0 12c0 1.94.46 3.77 1.29 5.38l4-3.1z" />
      <path fill="#EA4335" d="M12 4.77c1.76 0 3.34.61 4.58 1.8l3.44-3.44C17.95 1.19 15.24 0 12 0A12 12 0 0 0 1.29 6.62l4 3.1C6.23 6.88 8.88 4.77 12 4.77z" />
    </svg>
  );
}

function AppleGlyph() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <path d="M16.365 1.43c0 1.14-.465 2.21-1.225 3.01-.79.83-2.08 1.47-3.2 1.38-.14-1.1.4-2.26 1.16-3.04.79-.82 2.13-1.42 3.265-1.35zM20.76 17.16c-.53 1.22-.79 1.77-1.48 2.85-.96 1.5-2.31 3.37-3.99 3.39-1.49.02-1.88-.97-3.9-.96-2.02.01-2.45.98-3.94.96-1.68-.02-2.96-1.7-3.92-3.2-2.69-4.2-2.97-9.13-1.31-11.73 1.18-1.85 3.05-2.94 4.81-2.94 1.79 0 2.91.98 4.39.98 1.44 0 2.31-.98 4.37-.98 1.56 0 3.21.85 4.39 2.32-3.86 2.12-3.23 7.64.58 9.31z" />
    </svg>
  );
}

export default function AuthPage() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const clerk = useClerkBridge();
  const { user: storeUser, setUser, toast, hydrateFromBackend } = useStore();

  const notRegisteredNotice = params.get('not_registered') === '1';
  const [authMode, setAuthMode] = useState(
    notRegisteredNotice || params.get('mode') === 'register' || params.get('mode') === 'signup'
      ? 'register'
      : 'signin'
  );
  const [giMode, setGiMode] = useState('with_gi');
  const [form, setForm] = useState({
    storeName: '',
    phone: '',
    craft: 'pashmina',
    district: 'Srinagar',
    giId: '',
    skillDescription: '',
    terms: false
  });
  const [cardFile, setCardFile] = useState(null);
  const [cardPreviewUrl, setCardPreviewUrl] = useState('');
  const [dbSellerProfile, setDbSellerProfile] = useState(null);
  const [checkingDbStatus, setCheckingDbStatus] = useState(false);
  const [resubmitMode, setResubmitMode] = useState(params.get('edit') === '1');

  const [errMsg, setErrMsg] = useState(
    params.get('role_conflict') === '1'
      ? params.get('conflict_msg') ||
          'Role mismatch: this email is registered under a different role in HunarLink.'
      : notRegisteredNotice
        ? 'No registered HunarLink Artisan account was found for that email. Please register as an Artisan below first.'
        : ''
  );
  const [busyProvider, setBusyProvider] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  const clerkUser = clerk.clerkUser;
  const signedIn = Boolean(
    clerk.enabled && clerk.isSignedIn && clerkUser && storeUser && storeUser.isLoggedIn
  );

  useEffect(() => {
    if (params.get('role_conflict') === '1') {
      setAuthMode('signin');
      setErrMsg(
        params.get('conflict_msg') ||
          'Role mismatch: this email is registered under a different role in HunarLink.'
      );
    } else if (params.get('not_registered') === '1') {
      setAuthMode('register');
      setErrMsg(
        'No registered HunarLink Artisan account was found for that email. Please register as an Artisan below first.'
      );
    }
  }, [params]);
  const clerkEmail = clerkUser?.primaryEmailAddress?.emailAddress || '';
  const clerkName =
    clerkUser?.fullName ||
    [clerkUser?.firstName, clerkUser?.lastName].filter(Boolean).join(' ') ||
    '';

  useEffect(() => {
    const reset = (ev) => {
      setBusyProvider(null);
      if (ev?.persisted) {
        clearPendingClerkRole();
        clearPendingClerkAuthMode();
      }
    };
    window.addEventListener('pageshow', reset);
    window.addEventListener('focus', reset);
    return () => {
      window.removeEventListener('pageshow', reset);
      window.removeEventListener('focus', reset);
    };
  }, []);

  useEffect(() => {
    return () => {
      if (cardPreviewUrl) URL.revokeObjectURL(cardPreviewUrl);
    };
  }, [cardPreviewUrl]);

  const refreshLiveApplicationStatus = useCallback(async () => {
    if (!signedIn || !clerkUser) return;
    setCheckingDbStatus(true);
    try {
      if (canAttemptBackend() && clerk.getToken) {
        const token = await clerk.getToken();
        if (!token) return;
        const me = await fetchMyAuthProfile(token);
        const sp = me?.seller_profile || null;
        setDbSellerProfile(sp);

        if (sp) {
          setForm((prev) => ({
            ...prev,
            storeName: prev.storeName || sp.store_name || '',
            craft: sp.craft_specialty || prev.craft,
            district: sp.workshop_district || prev.district,
            phone: prev.phone || me?.phone || '',
            giId: prev.giId || sp.claimed_gi_authorized_user_no || ''
          }));
          setGiMode(sp.verification_path === 'GI' ? 'with_gi' : 'without_gi');

          const isApproved =
            Boolean(me?.artisan_verified) ||
            (sp.verification_status === 'APPROVED' && sp.profile_status === 'ACTIVE');
          const profileToSave = {
            artisanVerified: isApproved,
            verificationStatus: sp.verification_status,
            profileStatus: sp.profile_status,
            sellerProfileId: sp.seller_profile_id,
            business: sp.store_name || '',
            craft: sp.craft_specialty || 'pashmina',
            district: sp.workshop_district || 'Srinagar',
            phone: me.phone || '',
            giCertified: sp.verification_path === 'GI' && isApproved,
            giId: sp.claimed_gi_authorized_user_no || null,
            verificationPath: sp.verification_path,
            applicationNumber: sp.latest_application_number || null,
            reviewDecisionNotes: sp.review_decision_notes || null
          };
          saveClerkArtisanProfile(clerkUser.id, profileToSave);
          setUser(
            {
              id: clerkUser.id,
              clerkUserId: clerkUser.id,
              name: me?.display_name || clerkName || sp.store_name,
              fullName: me?.display_name || clerkName || sp.store_name,
              email: me?.email || clerkEmail,
              phone: me.phone || '',
              role: 'artisan',
              isLoggedIn: true,
              authProvider: 'clerk',
              sellerProfile: sp,
              ...profileToSave
            },
            { silent: true }
          );

          if (isApproved && params.get('edit') !== '1') {
            toast('Your Artisan Workshop has been verified by Admin! Entering Seller Studio.', 'success');
            await hydrateFromBackend(token);
            navigate('/seller', { replace: true });
          }
        }
      } else {
        const saved = readClerkArtisanProfile(clerkUser.id);
        if (saved?.artisanVerified && params.get('edit') !== '1') {
          navigate('/seller', { replace: true });
        }
      }
    } catch {
      /* User may not be synced yet; Step 2 submission will sync them first */
    } finally {
      setCheckingDbStatus(false);
    }
  }, [signedIn, clerkUser, clerk, clerkName, clerkEmail, params, navigate, setUser, toast, hydrateFromBackend]);

  useEffect(() => {
    if (signedIn && clerkUser) {
      refreshLiveApplicationStatus();
    }
  }, [signedIn, clerkUser?.id, refreshLiveApplicationStatus]);

  function handleCardFileChange(e) {
    const file = e.target.files?.[0] || null;
    setErrMsg('');
    if (cardPreviewUrl) {
      URL.revokeObjectURL(cardPreviewUrl);
      setCardPreviewUrl('');
    }
    if (!file) {
      setCardFile(null);
      return;
    }
    const allowedExt = /\.(jpe?g|png|webp|pdf)$/i.test(file.name || '');
    if (!allowedExt) {
      setErrMsg('Artisan Card must be a JPG, PNG, WebP image, or PDF document.');
      setCardFile(null);
      return;
    }
    if (file.size > 5 * 1024 * 1024) {
      setErrMsg('Artisan Card file must be under 5 MB.');
      setCardFile(null);
      return;
    }
    setCardFile(file);
    if (file.type && file.type.startsWith('image/')) {
      setCardPreviewUrl(URL.createObjectURL(file));
    }
  }

  async function launchOAuth(provider) {
    if (!clerk.enabled || !clerk.authenticateWithOAuth) {
      setErrMsg('Clerk authentication is not configured.');
      return;
    }
    setErrMsg('');
    setBusyProvider(provider);
    try {
      const res = await clerk.authenticateWithOAuth(provider, {
        role: 'artisan',
        mode: authMode === 'register' ? 'signup' : 'signin',
        redirectTo: '/auth?tab=verify'
      });
      if (res?.alreadySignedIn && res?.destination) {
        navigate(res.destination, { replace: true });
      }
    } catch (err) {
      setBusyProvider(null);
      setErrMsg(err?.message || 'Sign-in could not start.');
    }
  }

  async function submitVerification(e) {
    e.preventDefault();
    setErrMsg('');
    if (!signedIn || !clerkUser) {
      setErrMsg('Please sign in with Clerk first.');
      return;
    }
    if (!form.storeName.trim()) {
      setErrMsg('Enter your workshop or guild name.');
      return;
    }
    if (!form.phone.trim()) {
      setErrMsg('Enter your workshop contact phone number.');
      return;
    }
    if (giMode === 'with_gi' && !form.giId.trim()) {
      setErrMsg('Enter your GI Certificate / Authorized User Registration Number.');
      return;
    }
    if (giMode === 'without_gi' && !cardFile) {
      setErrMsg('Please upload your Artisan Card image (J&K Handicrafts / Pehchan / Workshop ID) for Admin verification.');
      return;
    }
    if (!form.terms) {
      setErrMsg('Please confirm the authenticity declaration.');
      return;
    }
    if (!canAttemptBackend()) {
      setErrMsg('FastAPI backend (:8000) is unreachable. Start the backend server so your application goes directly into the database.');
      return;
    }

    setSubmitting(true);
    try {
      const token = await clerk.getToken();
      if (!token) {
        throw new Error('Could not obtain Clerk session token. Please sign in again.');
      }

      // 1. Sync user account & DIRECT_SELLER role straight into `users` table
      await syncAuthenticatedUser(
        {
          email: clerkEmail,
          email_verified: Boolean(
            clerkUser.primaryEmailAddress?.verification?.status === 'verified'
          ),
          first_name: clerkUser.firstName || clerkName.split(' ')[0] || 'Artisan',
          last_name: clerkUser.lastName || null,
          display_name: clerkName || form.storeName.trim(),
          phone: form.phone.trim() || null,
          requested_role: 'artisan',
          auth_mode: 'sync'
        },
        token
      );

      // 2. Upload Artisan Card / GI Certificate to private scanned DB storage (`file_security_scans`)
      let uploadedScanId = null;
      if (cardFile) {
        const uploadScope = giMode === 'with_gi' ? 'gi_certificate' : 'artisan_card';
        const uploadRes = await uploadGuardrailDocument(cardFile, uploadScope, token);
        uploadedScanId = uploadRes.scan_id;
      }

      // 3. Stage application in `seller_verification_applications` + `seller_documents` + `seller_profiles` (SUBMITTED / DRAFT)
      const submitRes = await submitArtisanVerification(
        {
          store_name: form.storeName.trim(),
          craft_specialty: form.craft,
          workshop_district: form.district,
          verification_path: giMode === 'with_gi' ? 'GI' : 'NON_GI',
          claimed_gi_code: giMode === 'with_gi' ? form.giId.trim() : null,
          artisan_card_scan_id: uploadedScanId,
          skill_description: form.skillDescription.trim() || null,
          phone: form.phone.trim() || null
        },
        token
      );

      const sp = submitRes.seller_profile;
      const isApprovedNow =
        sp.verification_status === 'APPROVED' && sp.profile_status === 'ACTIVE';
      const pendingProfile = {
        artisanVerified: isApprovedNow,
        verificationStatus: sp.verification_status,
        profileStatus: sp.profile_status,
        sellerProfileId: sp.seller_profile_id,
        business: sp.store_name,
        craft: sp.craft_specialty,
        district: sp.workshop_district,
        phone: form.phone.trim(),
        giId: sp.claimed_gi_authorized_user_no || null,
        verificationPath: sp.verification_path,
        applicationNumber: submitRes.application_number
      };
      saveClerkArtisanProfile(clerkUser.id, pendingProfile);
      setUser(
        {
          id: clerkUser.id,
          clerkUserId: clerkUser.id,
          name: clerkName || sp.store_name,
          fullName: clerkName || sp.store_name,
          email: clerkEmail,
          phone: form.phone.trim(),
          role: 'artisan',
          isLoggedIn: true,
          authProvider: 'clerk',
          sellerProfile: sp,
          ...pendingProfile
        },
        { silent: true }
      );
      setDbSellerProfile({
        ...sp,
        latest_application_id: submitRes.application_id,
        latest_application_number: submitRes.application_number,
        latest_application_status: submitRes.application_status
      });
      setResubmitMode(false);
      await hydrateFromBackend(token);
      if (isApprovedNow) {
        toast('Artisan verification approved! Opening Artisan Workspace.', 'success');
        navigate('/seller', { replace: true });
      } else {
        toast(
          `Application ${submitRes.application_number} staged in database for Admin verification!`,
          'success'
        );
      }
    } catch (err) {
      setErrMsg(err?.message || 'Could not submit artisan verification to the database.');
    } finally {
      setSubmitting(false);
    }
  }

  const isPendingReview =
    signedIn &&
    dbSellerProfile &&
    ['SUBMITTED', 'UNDER_REVIEW', 'NEEDS_MORE_INFO'].includes(
      dbSellerProfile.verification_status
    ) &&
    !resubmitMode;

  const isRejected =
    signedIn &&
    dbSellerProfile &&
    dbSellerProfile.verification_status === 'REJECTED' &&
    !resubmitMode;

  return (
    <div className="portal-page login-page">
      <header className="up-header">
        <div className="up-header-inner">
          <Link to={signedIn ? '/' : '/login'} className="up-brand">
            <img
              src={`${import.meta.env.BASE_URL}img/brand/logo.svg`}
              alt=""
              className="up-emblem-mark"
              height="38"
            />
            <div>
              <div className="up-brand-title">HunarLink</div>
              <div className="up-brand-sub">Artisan Onboarding &amp; GI Verification</div>
            </div>
          </Link>
          <nav className="up-nav-links">
            <Link to="/" className="up-nav-pill">
              Storefront
            </Link>
            <Link to="/login" className="up-nav-pill">
              Buyer Sign In
            </Link>
            {signedIn && (
              <button
                type="button"
                className="up-nav-pill"
                onClick={async () => {
                  if (clerk.signOutClerk) await clerk.signOutClerk();
                  navigate('/login', { replace: true });
                }}
              >
                Sign out
              </button>
            )}
          </nav>
        </div>
      </header>

      <main className="login-shell" id="main-content">
        <div className="login-ambient" aria-hidden="true">
          <picture>
            {srcSetFor('img/artisan-loom-light.jpg') && (
              <source
                type="image/webp"
                srcSet={srcSetFor('img/artisan-loom-light.jpg')}
                sizes="100vw"
              />
            )}
            <img
              className="login-ambient-img"
              src={`${import.meta.env.BASE_URL}img/artisan-loom-light.jpg`}
              alt=""
            />
          </picture>
        </div>

        <section className="login-card">
          <div className="login-left">
            <div
              className="login-rail-photo"
              aria-hidden="true"
              style={{ backgroundImage: `url("${hdSrcFor('img/artisan-loom-dark.jpg')}")` }}
            />
            <div>
              <div className="login-pill">
                <IconSpark size={11} />
                Artisan Guild Registry
              </div>
              <h1>Kashmiri Artisan Verification</h1>
              <p>
                Every artisan on HunarLink verifies their identity via Clerk and submits either a
                GI Authorized User certificate or an Artisan Card image. Applications stay staged
                in our database until verified by an Administrator in the Admin Console.
              </p>
            </div>
            <ul className="login-perks">
              <li><IconBadgeCheck size={14} /> Staged in seller_verification_applications &amp; seller_documents</li>
              <li><IconShield size={14} /> Promoted to live Verified Artisans only after Admin approval</li>
            </ul>
          </div>

          <div className="login-right">
            {!signedIn ? (
              <>
                <div className="login-head">
                  <h2 className="login-title">
                    {authMode === 'register'
                      ? 'Step 1: Register Artisan Account'
                      : 'Step 1: Artisan Sign In'}
                  </h2>
                  <p className="login-sub">
                    {authMode === 'register'
                      ? 'New artisans register below. Already registered in our DB? Switch to Sign In — existing accounts cannot re-register.'
                      : 'Sign in with Google or Apple. Unverified artisans proceed straight to Verification.'}
                  </p>
                </div>

                <div className="seg" style={{ marginBottom: '0.9rem' }}>
                  <span className="seg-label">Action</span>
                  <div className="seg-track">
                    <button
                      type="button"
                      className={`seg-btn${authMode === 'signin' ? ' is-on' : ''}`}
                      onClick={() => {
                        setAuthMode('signin');
                        setErrMsg('');
                      }}
                    >
                      Sign In
                    </button>
                    <button
                      type="button"
                      className={`seg-btn${authMode === 'register' ? ' is-on' : ''}`}
                      onClick={() => {
                        setAuthMode('register');
                        setErrMsg('');
                      }}
                    >
                      Register
                    </button>
                  </div>
                </div>

                {errMsg && (
                  <div className="login-error show" role="alert" style={{ marginBottom: '0.85rem' }}>
                    {errMsg}
                  </div>
                )}
                {clerk.enabled ? (
                  <div className="login-social-section">
                    <div className="login-social-stack">
                      <button
                        type="button"
                        className="login-social-btn"
                        disabled={Boolean(busyProvider) || !clerk.isLoaded}
                        onClick={() => launchOAuth('google')}
                      >
                        <GoogleGlyph />
                        <span>
                          {busyProvider === 'google'
                            ? 'Redirecting…'
                            : authMode === 'register'
                              ? 'Register with Google'
                              : 'Sign in with Google'}
                        </span>
                      </button>
                      <button
                        type="button"
                        className="login-social-btn"
                        disabled={Boolean(busyProvider) || !clerk.isLoaded}
                        onClick={() => launchOAuth('apple')}
                      >
                        <AppleGlyph />
                        <span>
                          {busyProvider === 'apple'
                            ? 'Redirecting…'
                            : authMode === 'register'
                              ? 'Register with Apple'
                              : 'Sign in with Apple'}
                        </span>
                      </button>
                    </div>
                    <p className="login-footer-note" style={{ marginTop: '0.85rem' }}>
                      Prefer email code? Use{' '}
                      <Link to={authMode === 'register' ? '/register?role=artisan' : '/login?role=artisan'}>
                        Artisan Email {authMode === 'register' ? 'Registration' : 'Sign In'}
                      </Link>
                      .
                    </p>
                  </div>
                ) : (
                  <div className="login-error show" role="alert">
                    Clerk authentication must be configured in <code>app/.env.local</code>.
                  </div>
                )}
              </>
            ) : isPendingReview ? (
              <div>
                <div className="login-head">
                  <span
                    style={{
                      display: 'inline-block',
                      padding: '0.25rem 0.65rem',
                      borderRadius: '999px',
                      background: 'rgba(199, 91, 57, 0.12)',
                      color: '#a34121',
                      fontSize: '0.75rem',
                      fontWeight: 700,
                      letterSpacing: '0.04em',
                      textTransform: 'uppercase',
                      marginBottom: '0.6rem'
                    }}
                  >
                    ● Staged in Database • Awaiting Admin Verification
                  </span>
                  <h2 className="login-title">Application Under Admin Review</h2>
                  <p className="login-sub">
                    Your workshop <strong>{dbSellerProfile.store_name}</strong> is saved in{' '}
                    <code>seller_verification_applications</code> and awaiting inspection in the
                    Admin Panel. Once approved by Admin, your profile automatically goes live on the
                    Artisan Directory and unlocks your Seller Studio.
                  </p>
                </div>

                <div
                  style={{
                    background: '#faf6f0',
                    border: '1px solid rgba(0,0,0,0.08)',
                    borderRadius: '10px',
                    padding: '0.9rem 1rem',
                    fontSize: '0.85rem',
                    marginBottom: '1rem',
                    lineHeight: 1.65
                  }}
                >
                  <div>
                    <strong>Application #:</strong>{' '}
                    <code>{dbSellerProfile.latest_application_number || 'SUBMITTED'}</code>
                  </div>
                  <div>
                    <strong>Assigned Artisan UUID:</strong>{' '}
                    <code style={{ fontSize: '0.78rem' }}>{dbSellerProfile.seller_profile_id}</code>
                  </div>
                  <div>
                    <strong>Track:</strong>{' '}
                    {dbSellerProfile.verification_path === 'GI'
                      ? `GI Certified (${dbSellerProfile.claimed_gi_authorized_user_no || 'Submitted'})`
                      : 'Standard Artisan (Artisan Card Uploaded)'}
                  </div>
                  <div>
                    <strong>District &amp; Craft:</strong> {dbSellerProfile.workshop_district} •{' '}
                    {dbSellerProfile.craft_specialty}
                  </div>
                  <div>
                    <strong>Current DB Status:</strong>{' '}
                    <code>{dbSellerProfile.verification_status}</code> /{' '}
                    <code>{dbSellerProfile.profile_status}</code>
                  </div>
                </div>

                <div style={{ display: 'flex', gap: '0.65rem', flexWrap: 'wrap' }}>
                  <button
                    type="button"
                    className="btn-orange"
                    style={{ flex: 1, justifyContent: 'center' }}
                    disabled={checkingDbStatus}
                    onClick={refreshLiveApplicationStatus}
                  >
                    {checkingDbStatus ? 'Checking Database…' : 'Check Approval Status'}
                  </button>
                  <button
                    type="button"
                    className="btn-orange-outline"
                    onClick={() => setResubmitMode(true)}
                  >
                    Update / Re-upload Card
                  </button>
                </div>
              </div>
            ) : isRejected ? (
              <div>
                <div className="login-head">
                  <h2 className="login-title">Verification Requires Update</h2>
                  <p className="login-sub">
                    Your previous application for <strong>{dbSellerProfile.store_name}</strong> was
                    marked <code>REJECTED</code> during Admin review.
                  </p>
                </div>
                {dbSellerProfile.review_decision_notes && (
                  <div className="login-error show" style={{ marginBottom: '1rem' }}>
                    <strong>Admin Note:</strong> {dbSellerProfile.review_decision_notes}
                  </div>
                )}
                <button
                  type="button"
                  className="btn-orange"
                  style={{ width: '100%', justifyContent: 'center' }}
                  onClick={() => setResubmitMode(true)}
                >
                  Submit Updated Artisan Card &amp; Details
                </button>
              </div>
            ) : (
              <form onSubmit={submitVerification}>
                <div className="login-head">
                  <h2 className="login-title">Step 2: Workshop &amp; GI Verification</h2>
                  <p className="login-sub">
                    Signed in as <strong>{clerkName || clerkEmail}</strong> ({clerkEmail})
                  </p>
                </div>

                {errMsg && (
                  <div className="login-error show" role="alert" style={{ marginBottom: '0.85rem' }}>
                    {errMsg}
                  </div>
                )}

                <div className="seg" style={{ marginBottom: '1rem' }}>
                  <span className="seg-label">Track</span>
                  <div className="seg-track">
                    <button
                      type="button"
                      className={`seg-btn${giMode === 'with_gi' ? ' is-on' : ''}`}
                      onClick={() => setGiMode('with_gi')}
                    >
                      GI Certified
                    </button>
                    <button
                      type="button"
                      className={`seg-btn${giMode === 'without_gi' ? ' is-on' : ''}`}
                      onClick={() => setGiMode('without_gi')}
                    >
                      Standard Artisan
                    </button>
                  </div>
                </div>

                <div className="form-field">
                  <label className="up-label" htmlFor="art-store">
                    Workshop / Guild Name *
                  </label>
                  <input
                    id="art-store"
                    type="text"
                    className="up-input"
                    placeholder="e.g. Valley Loom Atelier"
                    required
                    value={form.storeName}
                    onChange={(e) => setForm((f) => ({ ...f, storeName: e.target.value }))}
                  />
                </div>

                <div className="up-grid-2">
                  <div className="form-field">
                    <label className="up-label" htmlFor="art-craft">Craft Guild *</label>
                    <select
                      id="art-craft"
                      className="up-select"
                      value={form.craft}
                      onChange={(e) => setForm((f) => ({ ...f, craft: e.target.value }))}
                    >
                      <option value="pashmina">Pashmina Textiles</option>
                      <option value="silk-rugs">Silk-on-Silk Rugs</option>
                      <option value="walnut">Walnut Woodcarving</option>
                      <option value="papier-mache">Papier-Mâché Art</option>
                      <option value="sozni">Sozni Embroidery</option>
                      <option value="copperware">Copperware</option>
                    </select>
                  </div>
                  <div className="form-field">
                    <label className="up-label" htmlFor="art-district">District *</label>
                    <select
                      id="art-district"
                      className="up-select"
                      value={form.district}
                      onChange={(e) => setForm((f) => ({ ...f, district: e.target.value }))}
                    >
                      <option value="Srinagar">Srinagar</option>
                      <option value="Budgam">Budgam</option>
                      <option value="Anantnag">Anantnag</option>
                      <option value="Baramulla">Baramulla</option>
                      <option value="Pulwama">Pulwama</option>
                      <option value="Ganderbal">Ganderbal</option>
                      <option value="Bandipora">Bandipora</option>
                    </select>
                  </div>
                </div>

                <div className="form-field">
                  <label className="up-label" htmlFor="art-phone">Workshop Phone *</label>
                  <input
                    id="art-phone"
                    type="tel"
                    className="up-input"
                    placeholder="+91 94190 XXXXX"
                    required
                    value={form.phone}
                    onChange={(e) => setForm((f) => ({ ...f, phone: e.target.value }))}
                  />
                </div>

                {giMode === 'with_gi' ? (
                  <>
                    <div className="form-field">
                      <label className="up-label" htmlFor="art-gi">
                        GI Registration / Authorized User Number *
                      </label>
                      <input
                        id="art-gi"
                        type="text"
                        className="up-input"
                        placeholder="e.g. GI-JK-PASH-8821"
                        required
                        value={form.giId}
                        onChange={(e) => setForm((f) => ({ ...f, giId: e.target.value }))}
                      />
                    </div>
                    <div className="form-field">
                      <label className="up-label" htmlFor="art-card-gi">
                        GI Certificate / Artisan Card Image (Optional — JPG, PNG, WebP, PDF)
                      </label>
                      <input
                        id="art-card-gi"
                        type="file"
                        accept=".jpg,.jpeg,.png,.webp,.pdf,image/jpeg,image/png,image/webp,application/pdf"
                        className="up-input"
                        onChange={handleCardFileChange}
                      />
                    </div>
                  </>
                ) : (
                  <div className="form-field">
                    <label className="up-label" htmlFor="art-card-std">
                      Artisan Card Image (J&amp;K Handicrafts / Pehchan Card) *
                    </label>
                    <input
                      id="art-card-std"
                      type="file"
                      required
                      accept=".jpg,.jpeg,.png,.webp,.pdf,image/jpeg,image/png,image/webp,application/pdf"
                      className="up-input"
                      onChange={handleCardFileChange}
                    />
                    <span style={{ display: 'block', fontSize: '0.76rem', opacity: 0.75, marginTop: '0.28rem' }}>
                      Sent directly to private DB storage for Admin verification before activating your artisan profile.
                    </span>
                  </div>
                )}

                {cardFile && (
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.75rem',
                      padding: '0.55rem 0.75rem',
                      borderRadius: '8px',
                      background: '#f7f3ec',
                      border: '1px solid rgba(0,0,0,0.08)',
                      marginBottom: '0.75rem',
                      fontSize: '0.8rem'
                    }}
                  >
                    {cardPreviewUrl && (
                      <img
                        src={cardPreviewUrl}
                        alt="Artisan card preview"
                        style={{
                          width: '54px',
                          height: '40px',
                          objectFit: 'cover',
                          borderRadius: '5px',
                          border: '1px solid rgba(0,0,0,0.12)'
                        }}
                      />
                    )}
                    <div style={{ minWidth: 0, flex: 1 }}>
                      <div style={{ fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {cardFile.name}
                      </div>
                      <div style={{ fontSize: '0.74rem', opacity: 0.7 }}>
                        {(cardFile.size / 1024).toFixed(1)} KB • Ready for ASIGS malware &amp; signature scan
                      </div>
                    </div>
                  </div>
                )}

                <div className="form-field">
                  <label className="up-label" htmlFor="art-bio">
                    Craft Lineage / Workshop Note (Optional)
                  </label>
                  <textarea
                    id="art-bio"
                    rows={2}
                    className="up-input"
                    placeholder="Briefly describe your loom, carving tradition, or family workshop…"
                    value={form.skillDescription}
                    onChange={(e) => setForm((f) => ({ ...f, skillDescription: e.target.value }))}
                  />
                </div>

                <label
                  style={{
                    display: 'flex',
                    alignItems: 'flex-start',
                    gap: '0.5rem',
                    fontSize: '0.84rem',
                    margin: '0.75rem 0 1rem'
                  }}
                >
                  <input
                    type="checkbox"
                    checked={form.terms}
                    onChange={(e) => setForm((f) => ({ ...f, terms: e.target.checked }))}
                  />
                  <span>
                    I declare that all craft details and Artisan Card / GI documents submitted are
                    genuine and produced in Jammu &amp; Kashmir.
                  </span>
                </label>

                <button
                  type="submit"
                  className="btn-orange"
                  style={{ width: '100%', justifyContent: 'center' }}
                  disabled={submitting}
                >
                  <IconCheck size={15} />
                  {submitting ? 'Uploading & staging in DB…' : 'Submit for Admin Verification'}
                  <IconArrowRight size={14} />
                </button>
              </form>
            )}
          </div>
        </section>
      </main>
    </div>
  );
}
