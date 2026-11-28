import React, { useCallback, useEffect, useRef, useState } from 'react';
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
  completeDigiLockerSandbox,
  fetchDigiLockerSession,
  fetchDigiLockerStatus,
  fetchGuardrailDocumentBlobUrl,
  fetchMyAuthProfile,
  startDigiLockerAuth,
  submitArtisanVerification,
  syncAuthenticatedUser
} from '../services/apiClient.js';
import { IconArrowRight, IconBadgeCheck, IconCheck, IconShield, IconSpark } from '../components/LineIcons.jsx';
import { hdSrcFor, srcSetFor } from '../data/imageVariants.js';
import { evaluatePassword } from '../utils/passwordPolicy.js';
import PasswordChecklist from '../components/PasswordChecklist.jsx';
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
  const [dlStatus, setDlStatus] = useState({ mode: 'sandbox', issuers: [] });
  const [dlVerification, setDlVerification] = useState(null);
  const [dlPreviewUrl, setDlPreviewUrl] = useState('');
  const [dlPreviewLoading, setDlPreviewLoading] = useState(false);
  const [dlBusy, setDlBusy] = useState(false);
  const [dlSandboxModal, setDlSandboxModal] = useState({
    open: false,
    verificationId: '',
    issuerId: 'in.gov.handicrafts',
    artisanCardNumber: '',
    cardHolderName: '',
    craftCategory: '',
    district: 'Srinagar',
    consentChecked: false,
    busy: false,
    error: ''
  });
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

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [signInMethod, setSignInMethod] = useState('password'); // 'password' | 'code' | 'forgot'
  const [forgotStep, setForgotStep] = useState('request'); // 'request' | 'reset'
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [code, setCode] = useState('');
  const [emailStep, setEmailStep] = useState('input'); // 'input' | 'verify'
  const [pendingFlow, setPendingFlow] = useState('signIn');
  const [emailBusy, setEmailBusy] = useState(false);

  const clerkUser = clerk.clerkUser;
  const signedIn = Boolean(
    clerk.enabled && clerk.isSignedIn && clerkUser && storeUser && storeUser.isLoggedIn
  );

  useEffect(() => {
    if (params.get('role_conflict') === '1') {
      setAuthMode('signin');
      setPendingFlow('signIn');
      setEmailStep('input');
      setCode('');
      setErrMsg(
        params.get('conflict_msg') ||
          'Role mismatch: this email is registered under a different role in HunarLink.'
      );
    } else if (params.get('already_registered') === '1') {
      setAuthMode('signin');
      setPendingFlow('signIn');
      setEmailStep('input');
      setCode('');
      setErrMsg(
        'This account already exists in HunarLink. Switched to Sign In — enter your email & password below to continue.'
      );
    } else if (params.get('account_deleted') === '1') {
      setAuthMode('register');
      setPendingFlow('signUp');
      setEmailStep('input');
      setCode('');
      setErrMsg(
        'Your previous HunarLink Artisan account was permanently deleted. Register below with email & password to create a new account.'
      );
    } else if (params.get('not_registered') === '1') {
      setAuthMode('register');
      setPendingFlow('signUp');
      setEmailStep('input');
      setCode('');
      setErrMsg(
        'No registered HunarLink Artisan account was found for that email. Register with your email & password below first.'
      );
    } else if (params.get('mode') === 'register' || params.get('mode') === 'signup') {
      setAuthMode('register');
    } else if (params.get('mode') === 'signin') {
      setAuthMode('signin');
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
    let active = true;
    if (!canAttemptBackend()) return undefined;
    fetchDigiLockerStatus()
      .then((res) => {
        if (active && res) setDlStatus(res);
      })
      .catch(() => {});
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    const dlErr = params.get('digilocker_error');
    if (dlErr) {
      setErrMsg(`DigiLocker authentication failed: ${dlErr}`);
    }
  }, [params]);

  const dlPreviewScanRef = useRef('');
  const dlPreviewObjUrlRef = useRef('');
  useEffect(() => {
    let active = true;
    const scanId = dlVerification?.file_scan_id || '';
    if (!scanId || !signedIn || !clerk.getToken) {
      dlPreviewScanRef.current = '';
      if (dlPreviewObjUrlRef.current) {
        URL.revokeObjectURL(dlPreviewObjUrlRef.current);
        dlPreviewObjUrlRef.current = '';
      }
      setDlPreviewUrl('');
      return undefined;
    }
    if (dlPreviewScanRef.current === scanId && dlPreviewObjUrlRef.current) {
      return undefined;
    }
    dlPreviewScanRef.current = scanId;
    setDlPreviewLoading(true);
    (async () => {
      try {
        const token = await clerk.getToken();
        if (!token || !active) return;
        const objUrl = await fetchGuardrailDocumentBlobUrl(scanId, token);
        if (!active) {
          if (objUrl) URL.revokeObjectURL(objUrl);
          return;
        }
        if (dlPreviewObjUrlRef.current) {
          URL.revokeObjectURL(dlPreviewObjUrlRef.current);
        }
        dlPreviewObjUrlRef.current = objUrl;
        setDlPreviewUrl(objUrl);
      } catch {
        if (active) setDlPreviewUrl('');
      } finally {
        if (active) setDlPreviewLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, [dlVerification?.file_scan_id, signedIn, clerk]);

  useEffect(() => {
    return () => {
      if (dlPreviewObjUrlRef.current) {
        URL.revokeObjectURL(dlPreviewObjUrlRef.current);
        dlPreviewObjUrlRef.current = '';
      }
    };
  }, []);

  const autoCheckedUserIdRef = useRef('');
  const checkingDbRef = useRef(false);

  const refreshLiveApplicationStatus = useCallback(async (forceRefresh = false) => {
    if (!signedIn || !clerkUser) return;
    if (checkingDbRef.current && !forceRefresh) return;
    checkingDbRef.current = true;
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
          if (sp.digilocker_verification_id && sp.artisan_card_scan_id) {
            setDlVerification((prev) =>
              prev?.verification_id === sp.digilocker_verification_id
                ? prev
                : {
                    verification_id: sp.digilocker_verification_id,
                    mode: sp.digilocker_mode || 'sandbox',
                    status: 'CONSUMED',
                    issuer_name: sp.digilocker_issuer_name || 'DigiLocker Artisan Card Issuer',
                    artisan_card_number: sp.digilocker_card_number || null,
                    card_holder_name: sp.digilocker_holder_name || null,
                    doc_uri: sp.digilocker_doc_uri || null,
                    file_scan_id: sp.artisan_card_scan_id,
                    fetched_at: sp.digilocker_fetched_at || null
                  }
            );
          }

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

          const needsUserUpdate =
            !storeUser ||
            Boolean(storeUser.artisanVerified) !== isApproved ||
            storeUser.verificationStatus !== sp.verification_status ||
            storeUser.profileStatus !== sp.profile_status ||
            storeUser.sellerProfileId !== sp.seller_profile_id ||
            storeUser.applicationNumber !== (sp.latest_application_number || null) ||
            storeUser.business !== (sp.store_name || '');

          if (needsUserUpdate) {
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
          }

          if (isApproved && params.get('edit') !== '1') {
            toast('Your Artisan Workshop has been verified by Admin! Entering Seller Studio.', 'success');
            await hydrateFromBackend(token);
            navigate('/seller', { replace: true });
          } else if (forceRefresh && !isApproved) {
            toast(`Status: ${sp.verification_status} — still awaiting Admin review in /admin.`, 'default');
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
      checkingDbRef.current = false;
      setCheckingDbStatus(false);
    }
  }, [signedIn, clerkUser, clerk, storeUser, clerkName, clerkEmail, params, navigate, setUser, toast, hydrateFromBackend]);

  useEffect(() => {
    if (!signedIn || !clerkUser?.id) {
      autoCheckedUserIdRef.current = '';
      return;
    }
    if (autoCheckedUserIdRef.current === clerkUser.id) return;
    autoCheckedUserIdRef.current = clerkUser.id;
    refreshLiveApplicationStatus();
  }, [signedIn, clerkUser?.id, refreshLiveApplicationStatus]);

  const dlQueryHandledRef = useRef('');
  useEffect(() => {
    const dlId = params.get('digilocker_id');
    const dlState = params.get('digilocker_status');
    if (!dlId || dlState !== 'fetched' || !signedIn || !clerk.getToken) return;
    if (dlQueryHandledRef.current === dlId) return;
    dlQueryHandledRef.current = dlId;

    let active = true;
    (async () => {
      try {
        const token = await clerk.getToken();
        if (!token || !active) return;
        const sess = await fetchDigiLockerSession(dlId, token);
        if (active && sess) {
          setDlVerification(sess);
          setResubmitMode(true);
          toast('Official Artisan Card fetched from DigiLocker!', 'success');
        }
      } catch (err) {
        if (active) {
          setErrMsg(err?.message || 'Could not load fetched DigiLocker Artisan Card session.');
        }
      }
    })();
    return () => {
      active = false;
    };
  }, [params, signedIn, clerk, toast]);

  async function handleStartDigiLocker() {
    setErrMsg('');
    if (!signedIn || !clerkUser) {
      setErrMsg('Please sign in with Clerk first.');
      return;
    }
    if (!canAttemptBackend()) {
      setErrMsg('FastAPI backend (:8000) is unreachable. Start the backend server to connect DigiLocker.');
      return;
    }
    setDlBusy(true);
    try {
      const token = await clerk.getToken();
      if (!token) throw new Error('Could not obtain Clerk session token. Please sign in again.');

      await syncAuthenticatedUser(
        {
          email: clerkEmail,
          email_verified: Boolean(
            clerkUser.primaryEmailAddress?.verification?.status === 'verified'
          ),
          first_name: clerkUser.firstName || clerkName.split(' ')[0] || 'Artisan',
          last_name: clerkUser.lastName || null,
          display_name: clerkName || form.storeName.trim() || 'Artisan',
          phone: form.phone.trim() || null,
          requested_role: 'artisan',
          auth_mode: 'sync'
        },
        token
      );

      const started = await startDigiLockerAuth({ return_to: '/auth?tab=verify' }, token);
      if (started.mode === 'live' && started.authorize_url) {
        window.location.assign(started.authorize_url);
        return;
      }

      const defaultIssuer = started.issuers?.[0]?.issuer_id || 'in.gov.handicrafts';
      setDlSandboxModal({
        open: true,
        verificationId: started.verification_id,
        issuerId: defaultIssuer,
        artisanCardNumber: dlVerification?.artisan_card_number || 'PEH-JK-2026-4812',
        cardHolderName: clerkName || form.storeName.trim() || 'Artisan Holder',
        craftCategory: form.craft || 'pashmina',
        district: form.district || 'Srinagar',
        consentChecked: false,
        busy: false,
        error: ''
      });
    } catch (err) {
      setErrMsg(err?.message || 'Could not initialize DigiLocker authentication.');
    } finally {
      setDlBusy(false);
    }
  }

  async function handleCompleteSandboxFetch(e) {
    e.preventDefault();
    if (!dlSandboxModal.consentChecked) {
      setDlSandboxModal((s) => ({
        ...s,
        error: 'Please check the DigiLocker consent box to share your Artisan Card with HunarLink.'
      }));
      return;
    }
    if (!dlSandboxModal.artisanCardNumber.trim() || !dlSandboxModal.cardHolderName.trim()) {
      setDlSandboxModal((s) => ({
        ...s,
        error: 'Enter your Artisan Card Number and Card Holder Name.'
      }));
      return;
    }
    setDlSandboxModal((s) => ({ ...s, busy: true, error: '' }));
    try {
      const token = await clerk.getToken();
      if (!token) throw new Error('Session expired. Please sign in again.');
      const res = await completeDigiLockerSandbox(
        {
          verification_id: dlSandboxModal.verificationId,
          issuer_id: dlSandboxModal.issuerId,
          artisan_card_number: dlSandboxModal.artisanCardNumber.trim(),
          card_holder_name: dlSandboxModal.cardHolderName.trim(),
          craft_category: dlSandboxModal.craftCategory.trim() || form.craft || 'Kashmiri Craft',
          district: dlSandboxModal.district.trim() || form.district || 'Srinagar'
        },
        token
      );
      setDlVerification(res);
      setDlSandboxModal((s) => ({ ...s, open: false, busy: false, error: '' }));
      toast('Artisan Card fetched via DigiLocker and stored for Admin verification!', 'success');
    } catch (err) {
      setDlSandboxModal((s) => ({
        ...s,
        busy: false,
        error: err?.message || 'Could not fetch Artisan Card from DigiLocker Sandbox.'
      }));
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

  async function handlePasswordSignIn(e) {
    e.preventDefault();
    if (!clerk.signInWithPassword) {
      setErrMsg('Clerk password authentication is unavailable.');
      return;
    }
    setErrMsg('');
    setEmailBusy(true);
    try {
      const res = await clerk.signInWithPassword(email, password, 'artisan');
      if (res?.status === 'complete') {
        navigate('/auth?tab=verify', { replace: true });
        return;
      }
      if (res?.status === 'needs_email_code' || res?.status === 'needs_second_factor') {
        setPendingFlow('signIn');
        setEmailStep('verify');
      }
    } catch (err) {
      if (err?.code === 'NOT_REGISTERED') {
        setAuthMode('register');
        setEmailStep('input');
        setErrMsg(
          err.message ||
            'No registered HunarLink Artisan account was found for that email. Register with your email & password below.'
        );
      } else {
        setErrMsg(err?.message || 'Invalid email or password.');
      }
    } finally {
      setEmailBusy(false);
    }
  }

  async function handleSendCode(e) {
    e.preventDefault();
    if (!clerk.sendEmailCode) {
      setErrMsg('Clerk email authentication is unavailable.');
      return;
    }
    if (authMode === 'register') {
      const pwCheck = evaluatePassword(password);
      if (!pwCheck.isValid) {
        setErrMsg(pwCheck.errorMessage);
        return;
      }
    }
    setErrMsg('');
    setEmailBusy(true);
    try {
      const res = await clerk.sendEmailCode(
        email,
        'artisan',
        authMode === 'register' ? 'signup' : 'signin',
        authMode === 'register' ? password : ''
      );
      if (res?.flow === 'complete') {
        navigate('/auth?tab=verify', { replace: true });
        return;
      }
      setPendingFlow(res.flow || (authMode === 'register' ? 'signUp' : 'signIn'));
      setEmailStep('verify');
    } catch (err) {
      if (err?.code === 'ALREADY_REGISTERED') {
        setAuthMode('signin');
        setEmailStep('input');
        setErrMsg(
          err.message ||
            'This email already exists in HunarLink. Switched to Sign In — please sign in below.'
        );
      } else if (err?.code === 'NOT_REGISTERED') {
        setAuthMode('register');
        setEmailStep('input');
        setErrMsg(
          err.message ||
            'No registered HunarLink Artisan account was found for that email. Register with your email & password below.'
        );
      } else {
        setErrMsg(err?.message || 'Could not send email verification code.');
      }
    } finally {
      setEmailBusy(false);
    }
  }

  async function handleVerifyCode(e) {
    e.preventDefault();
    if (!clerk.verifyEmailCode) return;
    if (pendingFlow === 'signUp' && password && !evaluatePassword(password).isValid) {
      setErrMsg(evaluatePassword(password).errorMessage);
      return;
    }
    setErrMsg('');
    setEmailBusy(true);
    try {
      await clerk.verifyEmailCode(code, pendingFlow, password);
      setEmailStep('input');
      setCode('');
      navigate('/auth?tab=verify', { replace: true });
    } catch (err) {
      if (err?.code === 'SWITCH_TO_SIGNIN') {
        setAuthMode('signin');
        setPendingFlow('signIn');
        setEmailStep('input');
        setCode('');
        setErrMsg(err.message);
      } else {
        setErrMsg(err?.message || 'Invalid or expired verification code.');
      }
    } finally {
      setEmailBusy(false);
    }
  }

  async function handleSendPasswordResetCode(e) {
    e.preventDefault();
    if (!clerk.sendPasswordResetCode) {
      setErrMsg('Clerk password reset is unavailable.');
      return;
    }
    setErrMsg('');
    setEmailBusy(true);
    try {
      await clerk.sendPasswordResetCode(email, 'artisan');
      setCode('');
      setNewPassword('');
      setConfirmPassword('');
      setForgotStep('reset');
      toast('Password reset code sent to your email.', 'success');
    } catch (err) {
      if (err?.code === 'NOT_REGISTERED') {
        setAuthMode('register');
        setSignInMethod('password');
        setForgotStep('request');
        setErrMsg(
          err.message ||
            'No registered HunarLink Artisan account was found for that email. Register below.'
        );
      } else {
        setErrMsg(err?.message || 'Could not send password reset code.');
      }
    } finally {
      setEmailBusy(false);
    }
  }

  async function handleCompletePasswordReset(e) {
    e.preventDefault();
    if (!clerk.completePasswordReset) {
      setErrMsg('Clerk password reset is unavailable.');
      return;
    }
    const pwCheck = evaluatePassword(newPassword);
    if (!pwCheck.isValid) {
      setErrMsg(pwCheck.errorMessage);
      return;
    }
    if (newPassword !== confirmPassword) {
      setErrMsg('New password and confirmation do not match.');
      return;
    }
    setErrMsg('');
    setEmailBusy(true);
    try {
      const res = await clerk.completePasswordReset(code, newPassword);
      if (res?.status === 'needs_second_factor') {
        setPendingFlow('signIn');
        setSignInMethod('code');
        setEmailStep('verify');
        setCode('');
        toast('Password updated! Enter the 2FA verification code sent to your email.', 'success');
        return;
      }
      setForgotStep('request');
      setSignInMethod('password');
      setCode('');
      setNewPassword('');
      setConfirmPassword('');
      toast('Password updated & signed in!', 'success');
      navigate('/auth?tab=verify', { replace: true });
    } catch (err) {
      setErrMsg(err?.message || 'Could not reset password.');
    } finally {
      setEmailBusy(false);
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
    if (!dlVerification?.verification_id || !dlVerification?.file_scan_id) {
      setErrMsg(
        'DigiLocker Artisan Card authentication is required for all artisans. Click "Authenticate & Fetch via DigiLocker" first.'
      );
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

      // 2. Stage application in `seller_verification_applications` + `seller_documents` + `seller_profiles` using DigiLocker verified card
      const submitRes = await submitArtisanVerification(
        {
          store_name: form.storeName.trim(),
          craft_specialty: form.craft,
          workshop_district: form.district,
          verification_path: giMode === 'with_gi' ? 'GI' : 'NON_GI',
          claimed_gi_code: giMode === 'with_gi' ? form.giId.trim() : null,
          digilocker_verification_id: dlVerification.verification_id,
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
        latest_application_status: submitRes.application_status,
        artisan_card_scan_id: dlVerification.file_scan_id,
        digilocker_verification_id: dlVerification.verification_id,
        digilocker_mode: dlVerification.mode,
        digilocker_issuer_name: dlVerification.issuer_name,
        digilocker_card_number: dlVerification.artisan_card_number,
        digilocker_holder_name: dlVerification.card_holder_name,
        digilocker_doc_uri: dlVerification.doc_uri
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
                      ? 'Register with email & password (or Google / Apple) below, then complete Workshop & GI verification.'
                      : 'Sign in with your email & password (or Google / Apple). Unverified artisans proceed straight to Verification.'}
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
                        setSignInMethod('password');
                        setForgotStep('request');
                        setEmailStep('input');
                        setCode('');
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
                        setSignInMethod('password');
                        setForgotStep('request');
                        setEmailStep('input');
                        setCode('');
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
                    {emailStep === 'input' ? (
                      authMode === 'signin' && signInMethod === 'forgot' ? (
                        forgotStep === 'request' ? (
                          <form onSubmit={handleSendPasswordResetCode}>
                            <div className="form-field">
                              <label className="up-label" htmlFor="artisan-clerk-forgot-email-input">
                                Account Email Address *
                              </label>
                              <input
                                id="artisan-clerk-forgot-email-input"
                                type="email"
                                className="up-input"
                                placeholder="artisan@example.com"
                                required
                                autoComplete="email"
                                value={email}
                                onChange={(e) => setEmail(e.target.value)}
                              />
                            </div>
                            <button
                              type="submit"
                              className="btn-orange"
                              style={{ width: '100%', justifyContent: 'center', marginTop: '0.25rem' }}
                              disabled={emailBusy}
                            >
                              <IconShield size={15} />
                              {emailBusy ? 'Sending reset code…' : 'Send Password Reset Code'}
                            </button>
                            <button
                              type="button"
                              className="btn-orange-outline"
                              style={{ width: '100%', justifyContent: 'center', marginTop: '0.5rem' }}
                              onClick={() => {
                                setSignInMethod('password');
                                setForgotStep('request');
                                setErrMsg('');
                              }}
                            >
                              Back to Sign In
                            </button>
                          </form>
                        ) : (
                          <form onSubmit={handleCompletePasswordReset}>
                            <div className="form-field">
                              <label className="up-label" htmlFor="artisan-clerk-reset-code-input">
                                6-Digit Reset Code sent to {email} *
                              </label>
                              <input
                                id="artisan-clerk-reset-code-input"
                                type="text"
                                inputMode="numeric"
                                className="up-input"
                                placeholder="Enter 6-digit reset code"
                                required
                                autoComplete="one-time-code"
                                value={code}
                                onChange={(e) => setCode(e.target.value)}
                              />
                            </div>
                            <div className="form-field">
                              <label className="up-label" htmlFor="artisan-clerk-reset-new-password-input">
                                New Password *
                              </label>
                              <input
                                id="artisan-clerk-reset-new-password-input"
                                type="password"
                                className="up-input"
                                placeholder="Create a new strong password"
                                required
                                minLength={8}
                                autoComplete="new-password"
                                value={newPassword}
                                onChange={(e) => setNewPassword(e.target.value)}
                              />
                              <PasswordChecklist password={newPassword} confirmPassword={confirmPassword} />
                            </div>
                            <div className="form-field">
                              <label className="up-label" htmlFor="artisan-clerk-reset-confirm-password-input">
                                Confirm New Password *
                              </label>
                              <input
                                id="artisan-clerk-reset-confirm-password-input"
                                type="password"
                                className="up-input"
                                placeholder="Re-enter your new password"
                                required
                                minLength={8}
                                autoComplete="new-password"
                                value={confirmPassword}
                                onChange={(e) => setConfirmPassword(e.target.value)}
                              />
                            </div>
                            <button
                              type="submit"
                              className="btn-orange"
                              style={{ width: '100%', justifyContent: 'center', marginTop: '0.25rem' }}
                              disabled={emailBusy}
                            >
                              <IconCheck size={15} />
                              {emailBusy ? 'Updating password…' : 'Reset Password & Sign In'}
                            </button>
                            <button
                              type="button"
                              className="btn-orange-outline"
                              style={{ width: '100%', justifyContent: 'center', marginTop: '0.5rem' }}
                              onClick={() => {
                                setForgotStep('request');
                                setCode('');
                                setErrMsg('');
                              }}
                            >
                              Resend code or change email
                            </button>
                          </form>
                        )
                      ) : authMode === 'signin' && signInMethod === 'password' ? (
                        <form onSubmit={handlePasswordSignIn}>
                          <div className="form-field">
                            <label className="up-label" htmlFor="artisan-clerk-email-input">
                              Email Address *
                            </label>
                            <input
                              id="artisan-clerk-email-input"
                              type="email"
                              className="up-input"
                              placeholder="artisan@example.com"
                              required
                              autoComplete="email"
                              value={email}
                              onChange={(e) => setEmail(e.target.value)}
                            />
                          </div>
                          <div className="form-field">
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '0.5rem' }}>
                              <label className="up-label" htmlFor="artisan-clerk-password-input" style={{ marginBottom: 0 }}>
                                Password *
                              </label>
                              <button
                                type="button"
                                onClick={() => {
                                  setSignInMethod('forgot');
                                  setForgotStep('request');
                                  setCode('');
                                  setErrMsg('');
                                }}
                                style={{
                                  border: 'none',
                                  background: 'transparent',
                                  color: '#c75b39',
                                  fontSize: '0.78rem',
                                  fontWeight: 600,
                                  cursor: 'pointer',
                                  padding: 0,
                                  textDecoration: 'underline'
                                }}
                              >
                                Forgot password?
                              </button>
                            </div>
                            <input
                              id="artisan-clerk-password-input"
                              type="password"
                              className="up-input"
                              placeholder="Enter your password"
                              required
                              autoComplete="current-password"
                              value={password}
                              onChange={(e) => setPassword(e.target.value)}
                            />
                          </div>
                          <button
                            type="submit"
                            className="btn-orange"
                            style={{ width: '100%', justifyContent: 'center', marginTop: '0.25rem' }}
                            disabled={emailBusy}
                          >
                            <IconShield size={15} />
                            {emailBusy ? 'Signing in…' : 'Sign In with Email & Password'}
                          </button>
                          <button
                            type="button"
                            className="btn-orange-outline"
                            style={{ width: '100%', justifyContent: 'center', marginTop: '0.5rem' }}
                            onClick={() => {
                              setSignInMethod('code');
                              setErrMsg('');
                            }}
                          >
                            Sign in with 6-digit email code instead
                          </button>
                        </form>
                      ) : (
                        <form onSubmit={handleSendCode}>
                          <div className="form-field">
                            <label className="up-label" htmlFor="artisan-clerk-email-input">
                              Email Address *
                            </label>
                            <input
                              id="artisan-clerk-email-input"
                              type="email"
                              className="up-input"
                              placeholder="artisan@example.com"
                              required
                              autoComplete="email"
                              value={email}
                              onChange={(e) => setEmail(e.target.value)}
                            />
                          </div>
                          {authMode === 'register' && (
                            <div className="form-field">
                              <label className="up-label" htmlFor="artisan-clerk-reg-password-input">
                                Create Password *
                              </label>
                              <input
                                id="artisan-clerk-reg-password-input"
                                type="password"
                                className="up-input"
                                placeholder="Create a strong password"
                                required
                                minLength={8}
                                autoComplete="new-password"
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                              />
                              <PasswordChecklist password={password} />
                            </div>
                          )}
                          <button
                            type="submit"
                            className="btn-orange"
                            style={{ width: '100%', justifyContent: 'center', marginTop: '0.25rem' }}
                            disabled={emailBusy}
                          >
                            <IconShield size={15} />
                            {emailBusy
                              ? authMode === 'register'
                                ? 'Creating account & sending verification code…'
                                : 'Checking database & sending code…'
                              : authMode === 'register'
                                ? 'Register with Email & Password'
                                : 'Send Sign-In Code'}
                          </button>
                          {authMode === 'signin' && (
                            <button
                              type="button"
                              className="btn-orange-outline"
                              style={{ width: '100%', justifyContent: 'center', marginTop: '0.5rem' }}
                              onClick={() => {
                                setSignInMethod('password');
                                setErrMsg('');
                              }}
                            >
                              Sign in with Email &amp; Password instead
                            </button>
                          )}
                        </form>
                      )
                    ) : (
                      <form onSubmit={handleVerifyCode}>
                        <div className="form-field">
                          <label className="up-label" htmlFor="artisan-clerk-code-input">
                            6-Digit Verification Code sent to {email} *
                          </label>
                          <input
                            id="artisan-clerk-code-input"
                            type="text"
                            inputMode="numeric"
                            className="up-input"
                            placeholder="Enter 6-digit code"
                            required
                            autoComplete="one-time-code"
                            value={code}
                            onChange={(e) => setCode(e.target.value)}
                          />
                        </div>
                        {pendingFlow === 'signUp' && !evaluatePassword(password).isValid && (
                          <div className="form-field">
                            <label className="up-label" htmlFor="artisan-clerk-verify-password-input">
                              Create Password *
                            </label>
                            <input
                              id="artisan-clerk-verify-password-input"
                              type="password"
                              className="up-input"
                              placeholder="Create a strong password"
                              required
                              minLength={8}
                              autoComplete="new-password"
                              value={password}
                              onChange={(e) => setPassword(e.target.value)}
                            />
                            <PasswordChecklist password={password} />
                          </div>
                        )}
                        <button
                          type="submit"
                          className="btn-orange"
                          style={{ width: '100%', justifyContent: 'center' }}
                          disabled={emailBusy}
                        >
                          <IconCheck size={15} />
                          {emailBusy
                            ? 'Verifying code…'
                            : authMode === 'register'
                              ? 'Verify Email & Continue to Workshop Setup'
                              : 'Verify & Sign In'}
                        </button>
                        <button
                          type="button"
                          className="btn-orange-outline"
                          style={{ width: '100%', justifyContent: 'center', marginTop: '0.5rem' }}
                          onClick={() => {
                            setEmailStep('input');
                            setCode('');
                            setErrMsg('');
                          }}
                        >
                          Use a different email
                        </button>
                      </form>
                    )}

                    <div className="login-social-divider" aria-hidden="true">
                      <span>or continue with</span>
                    </div>

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
                      : 'Standard Artisan'}
                  </div>
                  <div>
                    <strong>DigiLocker Proof:</strong>{' '}
                    {dbSellerProfile.digilocker_card_number || 'Verified Card'} •{' '}
                    {dbSellerProfile.digilocker_issuer_name || 'DigiLocker Issuer'}{' '}
                    <span
                      style={{
                        fontSize: '0.72rem',
                        fontWeight: 700,
                        padding: '0.1rem 0.4rem',
                        borderRadius: '4px',
                        background:
                          dbSellerProfile.digilocker_mode === 'live' ? '#e7f5ee' : '#eef2ff',
                        color: dbSellerProfile.digilocker_mode === 'live' ? '#166534' : '#3730a3'
                      }}
                    >
                      {(dbSellerProfile.digilocker_mode || 'sandbox').toUpperCase()}
                    </span>
                  </div>
                  {dlPreviewUrl && (
                    <div style={{ marginTop: '0.5rem' }}>
                      <img
                        src={dlPreviewUrl}
                        alt="Fetched DigiLocker Artisan Card"
                        style={{
                          width: '100%',
                          maxWidth: '280px',
                          borderRadius: '8px',
                          border: '1px solid rgba(0,0,0,0.12)'
                        }}
                      />
                    </div>
                  )}
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
                    onClick={() => refreshLiveApplicationStatus(true)}
                  >
                    {checkingDbStatus ? 'Checking Database…' : 'Check Approval Status'}
                  </button>
                  <button
                    type="button"
                    className="btn-orange-outline"
                    onClick={() => setResubmitMode(true)}
                  >
                    Update / Re-fetch DigiLocker Card
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

                {giMode === 'with_gi' && (
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
                )}

                <div
                  className="form-field"
                  style={{
                    padding: '0.9rem 1rem',
                    borderRadius: '12px',
                    background: dlVerification ? '#f1f9f4' : '#f4f7fb',
                    border: dlVerification
                      ? '1px solid rgba(22, 101, 52, 0.25)'
                      : '1px solid rgba(30, 64, 175, 0.2)',
                    marginBottom: '0.95rem'
                  }}
                >
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      gap: '0.5rem',
                      marginBottom: '0.45rem'
                    }}
                  >
                    <span className="up-label" style={{ marginBottom: 0 }}>
                      DigiLocker Artisan Card Authentication *
                    </span>
                    <span
                      style={{
                        fontSize: '0.72rem',
                        fontWeight: 700,
                        padding: '0.12rem 0.48rem',
                        borderRadius: '999px',
                        background: dlStatus?.mode === 'live' ? '#e7f5ee' : '#e0e7ff',
                        color: dlStatus?.mode === 'live' ? '#166534' : '#3730a3'
                      }}
                    >
                      {dlStatus?.mode === 'live' ? 'DigiLocker Live OAuth' : 'DigiLocker Sandbox'}
                    </span>
                  </div>

                  {!dlVerification ? (
                    <>
                      <p style={{ fontSize: '0.82rem', margin: '0 0 0.7rem', color: '#334155', lineHeight: 1.45 }}>
                        Required for all registering artisans (both GI Certified &amp; Standard):
                        authenticate via DigiLocker to automatically fetch your official Artisan Card
                        (Pehchan / J&amp;K Handicrafts) for Admin confirmation. Manual file uploads
                        are disabled to prevent forged documents.
                      </p>
                      <button
                        type="button"
                        className="btn-orange-outline"
                        style={{
                          width: '100%',
                          justifyContent: 'center',
                          borderColor: '#1d4ed8',
                          color: '#1d4ed8',
                          background: '#ffffff'
                        }}
                        disabled={dlBusy}
                        onClick={handleStartDigiLocker}
                      >
                        <IconShield size={15} />
                        {dlBusy
                          ? 'Connecting to DigiLocker…'
                          : 'Authenticate & Fetch Artisan Card via DigiLocker'}
                      </button>
                    </>
                  ) : (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.65rem' }}>
                      <div style={{ fontSize: '0.82rem', color: '#14532d', fontWeight: 600 }}>
                        ✓ Artisan Card Fetched from DigiLocker ({(dlVerification.mode || 'sandbox').toUpperCase()})
                      </div>
                      <div style={{ fontSize: '0.8rem', lineHeight: 1.5, color: '#1f2937' }}>
                        <div>
                          <strong>Card No:</strong>{' '}
                          <code>{dlVerification.artisan_card_number || 'VERIFIED'}</code>
                        </div>
                        <div>
                          <strong>Holder:</strong> {dlVerification.card_holder_name || clerkName}
                        </div>
                        <div>
                          <strong>Issuer:</strong> {dlVerification.issuer_name}
                        </div>
                        {dlVerification.doc_uri && (
                          <div style={{ wordBreak: 'break-all' }}>
                            <strong>DigiLocker URI:</strong> <code>{dlVerification.doc_uri}</code>
                          </div>
                        )}
                      </div>
                      {dlPreviewLoading ? (
                        <div style={{ fontSize: '0.78rem', opacity: 0.75 }}>
                          Loading fetched Artisan Card preview…
                        </div>
                      ) : (
                        dlPreviewUrl && (
                          <img
                            src={dlPreviewUrl}
                            alt="DigiLocker fetched Artisan Card"
                            style={{
                              width: '100%',
                              maxWidth: '300px',
                              borderRadius: '8px',
                              border: '1px solid rgba(0,0,0,0.14)'
                            }}
                          />
                        )
                      )}
                      <div>
                        <button
                          type="button"
                          className="btn-orange-outline"
                          style={{ fontSize: '0.78rem', padding: '0.35rem 0.7rem' }}
                          disabled={dlBusy}
                          onClick={handleStartDigiLocker}
                        >
                          {dlBusy ? 'Connecting…' : 'Re-fetch via DigiLocker'}
                        </button>
                      </div>
                    </div>
                  )}
                </div>

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
                    I declare that all craft details and the DigiLocker Artisan Card presented are
                    genuine and produced in Jammu &amp; Kashmir.
                  </span>
                </label>

                <button
                  type="submit"
                  className="btn-orange"
                  style={{ width: '100%', justifyContent: 'center' }}
                  disabled={submitting || !dlVerification}
                >
                  <IconCheck size={15} />
                  {submitting
                    ? 'Staging DigiLocker verification in DB…'
                    : 'Submit for Admin Verification'}
                  <IconArrowRight size={14} />
                </button>
              </form>
            )}
          </div>
        </section>
      </main>

      {dlSandboxModal.open && (
        <div
          className="up-modal-backdrop"
          role="dialog"
          aria-modal="true"
          aria-labelledby="dl-sandbox-title"
          onClick={() => !dlSandboxModal.busy && setDlSandboxModal((s) => ({ ...s, open: false }))}
        >
          <div
            className="up-modal"
            style={{ maxWidth: '500px' }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="up-modal-head" style={{ borderBottomColor: 'rgba(29, 78, 216, 0.16)' }}>
              <div>
                <span
                  style={{
                    display: 'inline-block',
                    fontSize: '0.7rem',
                    fontWeight: 700,
                    padding: '0.15rem 0.5rem',
                    borderRadius: '999px',
                    background: '#e0e7ff',
                    color: '#3730a3',
                    marginBottom: '0.3rem'
                  }}
                >
                  DIGILOCKER SANDBOX CONSENT (NON-PROD)
                </span>
                <h3 id="dl-sandbox-title" style={{ margin: 0 }}>
                  MeriPehchaan / DigiLocker Artisan Card Consent
                </h3>
              </div>
              <button
                type="button"
                className="up-modal-close"
                aria-label="Close"
                disabled={dlSandboxModal.busy}
                onClick={() => setDlSandboxModal((s) => ({ ...s, open: false }))}
              >
                ×
              </button>
            </div>
            <form onSubmit={handleCompleteSandboxFetch} style={{ padding: '1rem 1.25rem 1.25rem' }}>
              <p style={{ fontSize: '0.82rem', color: '#475569', marginTop: 0, lineHeight: 1.45 }}>
                Confirm consent below to pull your digitally signed Artisan Card into HunarLink&apos;s
                private verification vault for Admin review. (Live OAuth engages automatically when{' '}
                <code>DIGILOCKER_CLIENT_ID</code> is configured.)
              </p>
              {dlSandboxModal.error && (
                <div className="login-error show" style={{ marginBottom: '0.75rem' }}>
                  {dlSandboxModal.error}
                </div>
              )}

              <div className="form-field">
                <label className="up-label" htmlFor="dl-issuer">Issuing Authority *</label>
                <select
                  id="dl-issuer"
                  className="up-select"
                  value={dlSandboxModal.issuerId}
                  onChange={(e) => setDlSandboxModal((s) => ({ ...s, issuerId: e.target.value }))}
                >
                  {(dlStatus?.issuers?.length
                    ? dlStatus.issuers
                    : [
                        {
                          issuer_id: 'in.gov.handicrafts',
                          label: 'DC (Handicrafts) — Pehchan Artisan Card'
                        },
                        {
                          issuer_id: 'in.gov.jk.handicrafts',
                          label: 'Directorate of Handicrafts & Handloom, J&K'
                        }
                      ]
                  ).map((iss) => (
                    <option key={iss.issuer_id} value={iss.issuer_id}>
                      {iss.label || iss.issuer_name}
                    </option>
                  ))}
                </select>
              </div>

              <div className="form-field">
                <label className="up-label" htmlFor="dl-card-no">Pehchan / Artisan Card Number *</label>
                <input
                  id="dl-card-no"
                  type="text"
                  className="up-input"
                  required
                  placeholder="e.g. PEH-JK-2026-4812"
                  value={dlSandboxModal.artisanCardNumber}
                  onChange={(e) =>
                    setDlSandboxModal((s) => ({ ...s, artisanCardNumber: e.target.value }))
                  }
                />
              </div>

              <div className="form-field">
                <label className="up-label" htmlFor="dl-holder">Card Holder Full Name *</label>
                <input
                  id="dl-holder"
                  type="text"
                  className="up-input"
                  required
                  value={dlSandboxModal.cardHolderName}
                  onChange={(e) =>
                    setDlSandboxModal((s) => ({ ...s, cardHolderName: e.target.value }))
                  }
                />
              </div>

              <div className="up-grid-2">
                <div className="form-field">
                  <label className="up-label" htmlFor="dl-craft">Craft Category *</label>
                  <input
                    id="dl-craft"
                    type="text"
                    className="up-input"
                    required
                    value={dlSandboxModal.craftCategory}
                    onChange={(e) =>
                      setDlSandboxModal((s) => ({ ...s, craftCategory: e.target.value }))
                    }
                  />
                </div>
                <div className="form-field">
                  <label className="up-label" htmlFor="dl-dist">District *</label>
                  <input
                    id="dl-dist"
                    type="text"
                    className="up-input"
                    required
                    value={dlSandboxModal.district}
                    onChange={(e) =>
                      setDlSandboxModal((s) => ({ ...s, district: e.target.value }))
                    }
                  />
                </div>
              </div>

              <label
                style={{
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: '0.5rem',
                  fontSize: '0.82rem',
                  margin: '0.75rem 0 1rem'
                }}
              >
                <input
                  type="checkbox"
                  checked={dlSandboxModal.consentChecked}
                  onChange={(e) =>
                    setDlSandboxModal((s) => ({ ...s, consentChecked: e.target.checked }))
                  }
                />
                <span>
                  I authorize <strong>DigiLocker (MeriPehchaan)</strong> to share my issued Artisan
                  Card document &amp; issuer metadata with HunarLink for seller verification.
                </span>
              </label>

              <div style={{ display: 'flex', gap: '0.65rem', justifyContent: 'flex-end' }}>
                <button
                  type="button"
                  className="btn-orange-outline"
                  disabled={dlSandboxModal.busy}
                  onClick={() => setDlSandboxModal((s) => ({ ...s, open: false }))}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn-orange"
                  disabled={dlSandboxModal.busy}
                >
                  {dlSandboxModal.busy ? 'Fetching Artisan Card…' : 'Authorize & Fetch Card'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
