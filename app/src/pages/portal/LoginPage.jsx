import React, { useEffect, useState } from 'react';
import { Link, useLocation, useNavigate, useSearchParams } from 'react-router-dom';
import { useStore } from '../../state/StoreContext.jsx';
import {
  clearPendingClerkAuthMode,
  clearPendingClerkRole,
  useClerkBridge
} from '../../data/clerkConfig.js';
import {
  IconArrowRight,
  IconBadgeCheck,
  IconBookmark,
  IconCheck,
  IconShield,
  IconSpark,
  IconTruck,
  IconUser
} from '../../components/LineIcons.jsx';
import { hdSrcFor, srcSetFor } from '../../data/imageVariants.js';
import '../../styles/portal.css';

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

export default function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const [params] = useSearchParams();
  const { user, toast } = useStore();
  const clerk = useClerkBridge();

  const isRegisterRoute = /^\/register(\.html)?$/i.test(location.pathname);
  const initialRole = params.get('role') === 'artisan' ? 'artisan' : 'user';
  const initialMode =
    isRegisterRoute ||
    params.get('mode') === 'register' ||
    params.get('mode') === 'signup'
      ? 'register'
      : 'signin';
  const alreadyRegisteredNotice = params.get('already_registered') === '1';
  const notRegisteredNotice = params.get('not_registered') === '1';
  const accountDeletedNotice = params.get('account_deleted') === '1';
  const roleConflictNotice = params.get('role_conflict') === '1';
  const conflictMsg = params.get('conflict_msg') || '';
  const nextUrl = params.get('next') || '/';

  const [authMode, setAuthMode] = useState(
    notRegisteredNotice || accountDeletedNotice ? 'register' : initialMode
  ); // 'signin' | 'register'
  const [role, setRole] = useState(initialRole);
  const [errMsg, setErrMsg] = useState(
    roleConflictNotice
      ? conflictMsg || 'This account is registered under a different role in HunarLink.'
      : accountDeletedNotice
        ? 'Your previous HunarLink account was permanently deleted. Register below if you want to create a brand-new account.'
        : alreadyRegisteredNotice
          ? 'This account already exists in HunarLink. You cannot register again — please Sign In below.'
          : notRegisteredNotice
            ? 'No registered HunarLink account was found for that email. Please register first below.'
            : ''
  );
  const [busyProvider, setBusyProvider] = useState(null);

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

  const signedIn = clerk.enabled
    ? Boolean(clerk.isSignedIn && user && user.isLoggedIn)
    : Boolean(user && user.authProvider === 'clerk' && user.isLoggedIn);
  const isArtisanSession = Boolean(
    user && (user.role === 'seller' || user.role === 'artisan')
  );
  const isVerifiedArtisan = Boolean(isArtisanSession && user?.artisanVerified);

  useEffect(() => {
    if (params.get('role_conflict') === '1') {
      setAuthMode('signin');
      setPendingFlow('signIn');
      setEmailStep('input');
      setCode('');
      setErrMsg(
        params.get('conflict_msg') ||
          'Role mismatch: this email is registered under a different HunarLink role.'
      );
    } else if (params.get('already_registered') === '1') {
      setAuthMode('signin');
      setPendingFlow('signIn');
      setEmailStep('input');
      setCode('');
      setErrMsg(
        'This account already exists in HunarLink. Switched to Sign In — enter your email or use Google below to continue.'
      );
    } else if (params.get('account_deleted') === '1') {
      setAuthMode('register');
      setPendingFlow('signUp');
      setEmailStep('input');
      setCode('');
      setErrMsg(
        'Your previous HunarLink account was permanently deleted. Register below if you want to create a brand-new account.'
      );
    } else if (params.get('not_registered') === '1') {
      setAuthMode('register');
      setPendingFlow('signUp');
      setEmailStep('input');
      setCode('');
      setErrMsg(
        'No registered HunarLink account was found for that email. Please register first below.'
      );
    } else if (isRegisterRoute) {
      setAuthMode('register');
    } else if (params.get('mode') === 'register' || params.get('mode') === 'signup') {
      setAuthMode('register');
    } else if (params.get('mode') === 'signin') {
      setAuthMode('signin');
    } else {
      setAuthMode('signin');
    }
  }, [isRegisterRoute, params]);

  useEffect(() => {
    if (signedIn && isArtisanSession && !isVerifiedArtisan) {
      navigate('/auth?tab=verify', { replace: true });
    }
  }, [signedIn, isArtisanSession, isVerifiedArtisan, navigate]);

  useEffect(() => {
    const resetBusy = (event) => {
      setBusyProvider(null);
      if (event?.persisted) {
        clearPendingClerkRole();
        clearPendingClerkAuthMode();
      }
    };
    const onVisChange = () => {
      if (document.visibilityState === 'visible') setBusyProvider(null);
    };
    window.addEventListener('pageshow', resetBusy);
    window.addEventListener('focus', resetBusy);
    document.addEventListener('visibilitychange', onVisChange);
    return () => {
      window.removeEventListener('pageshow', resetBusy);
      window.removeEventListener('focus', resetBusy);
      document.removeEventListener('visibilitychange', onVisChange);
    };
  }, []);

  async function startOAuth(provider) {
    if (!clerk.enabled || !clerk.authenticateWithOAuth) {
      setErrMsg('Clerk authentication is required. Configure VITE_CLERK_PUBLISHABLE_KEY.');
      return;
    }
    setErrMsg('');
    setBusyProvider(provider);
    try {
      const res = await clerk.authenticateWithOAuth(provider, {
        role: role === 'artisan' ? 'artisan' : 'user',
        mode: authMode === 'register' ? 'signup' : 'signin',
        redirectTo: role === 'artisan' ? '/auth?tab=verify' : nextUrl || '/'
      });
      if (res?.alreadySignedIn && res?.destination) {
        navigate(res.destination, { replace: true });
      }
    } catch (err) {
      setBusyProvider(null);
      setErrMsg(err?.message || 'Could not start sign-in.');
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
      const res = await clerk.signInWithPassword(
        email,
        password,
        role === 'artisan' ? 'artisan' : 'buyer'
      );
      if (res?.status === 'complete') {
        navigate(role === 'artisan' ? '/auth?tab=verify' : nextUrl || '/', { replace: true });
        return;
      }
      if (res?.status === 'needs_email_code' || res?.status === 'needs_second_factor') {
        setPendingFlow('signIn');
        setEmailStep('verify');
      }
    } catch (err) {
      if (err?.code === 'NOT_REGISTERED') {
        setEmailStep('input');
        setAuthMode('register');
        setErrMsg(
          err.message ||
            (role === 'artisan'
              ? 'No registered HunarLink Artisan account was found for that email. Register with your email & password below.'
              : 'No registered HunarLink Buyer account was found for that email. Register with your email & password below.')
        );
        navigate(
          role === 'artisan'
            ? '/register?role=artisan&not_registered=1'
            : '/register?not_registered=1',
          { replace: true }
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
    if (authMode === 'register' && password.length < 15) {
      setErrMsg('Password must be at least 15 characters long.');
      return;
    }
    setErrMsg('');
    setEmailBusy(true);
    try {
      const res = await clerk.sendEmailCode(
        email,
        role === 'artisan' ? 'artisan' : 'buyer',
        authMode === 'register' ? 'signup' : 'signin',
        authMode === 'register' ? password : ''
      );
      if (res?.flow === 'complete') {
        navigate(role === 'artisan' ? '/auth?tab=verify' : nextUrl || '/', { replace: true });
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
        navigate(role === 'artisan' ? '/login?role=artisan' : '/login', { replace: true });
      } else if (err?.code === 'NOT_REGISTERED') {
        setEmailStep('input');
        setAuthMode('register');
        setErrMsg(
          err.message ||
            (role === 'artisan'
              ? 'No registered HunarLink Artisan account was found for that email. Register with your email & password below.'
              : 'No registered HunarLink Buyer account was found for that email. Register with your email & password below.')
        );
        navigate(
          role === 'artisan'
            ? '/register?role=artisan&not_registered=1'
            : '/register?not_registered=1',
          { replace: true }
        );
      } else {
        setErrMsg(err?.message || 'Could not send email code. Try Sign in with Google.');
      }
    } finally {
      setEmailBusy(false);
    }
  }

  async function handleVerifyCode(e) {
    e.preventDefault();
    if (!clerk.verifyEmailCode) return;
    if (pendingFlow === 'signUp' && password && password.length < 15) {
      setErrMsg('Password must be at least 15 characters long.');
      return;
    }
    setErrMsg('');
    setEmailBusy(true);
    try {
      await clerk.verifyEmailCode(code, pendingFlow, password);
      navigate(role === 'artisan' ? '/auth?tab=verify' : nextUrl || '/', { replace: true });
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
      await clerk.sendPasswordResetCode(email, role === 'artisan' ? 'artisan' : 'buyer');
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
            (role === 'artisan'
              ? 'No registered HunarLink Artisan account was found for that email. Register below.'
              : 'No registered HunarLink Buyer account was found for that email. Register below.')
        );
        navigate(
          role === 'artisan'
            ? '/register?role=artisan&not_registered=1'
            : '/register?not_registered=1',
          { replace: true }
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
    if (newPassword.length < 15) {
      setErrMsg('New password must be at least 15 characters long.');
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
      navigate(role === 'artisan' ? '/auth?tab=verify' : nextUrl || '/', { replace: true });
    } catch (err) {
      setErrMsg(err?.message || 'Could not reset password.');
    } finally {
      setEmailBusy(false);
    }
  }

  async function signOutHere() {
    if (clerk.signOutClerk) await clerk.signOutClerk();
    toast('Signed out cleanly');
  }

  return (
    <div className="portal-page login-page">
      <header className="up-header">
        <div className="up-header-inner">
          <Link to="/" className="up-brand">
            <img
              src={`${import.meta.env.BASE_URL}img/brand/logo.svg`}
              alt=""
              className="up-emblem-mark"
              height="38"
            />
            <div>
              <div className="up-brand-title">HunarLink</div>
              <div className="up-brand-sub">
                {signedIn
                  ? isArtisanSession
                    ? 'Artisan Workspace'
                    : 'Verified Account'
                  : 'My Account'}
              </div>
            </div>
          </Link>
          <nav className="up-nav-links">
            <Link to="/" className="up-nav-pill">
              <IconArrowRight size={13} className="login-back-arrow" /> Storefront
            </Link>
            {signedIn && (
              <Link
                to={
                  isArtisanSession
                    ? isVerifiedArtisan
                      ? '/seller'
                      : '/auth?tab=verify'
                    : '/profile'
                }
                className="up-nav-pill"
              >
                {isArtisanSession
                  ? isVerifiedArtisan
                    ? 'Workspace'
                    : 'Verify Artisan'
                  : 'My Profile'}
              </Link>
            )}
            {signedIn ? (
              <button type="button" className="up-nav-pill" onClick={signOutHere}>
                Sign out
              </button>
            ) : (
              <Link to="/admin" className="login-header-hint login-admin-link">
                Admin Login
              </Link>
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
              loading="eager"
              decoding="async"
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
              <div className="login-pill" id="left-pill">
                <IconSpark size={11} />
                {role === 'artisan' ? 'Artisan Guild Access' : 'Verified Buyer Access'}
              </div>
              <h1 id="left-heading">
                {role === 'artisan'
                  ? 'Your craft, verified in the registry.'
                  : 'Sign in to enter HunarLink'}
              </h1>
              <p id="left-desc">
                {role === 'artisan'
                  ? 'Sign in with Clerk to complete GI / Artisan verification, manage real listings, and track orders directly from your workshop.'
                  : 'Every HunarLink marketplace listing, artisan dossier, and order is secured behind real verified identity.'}
              </p>
            </div>

            <ul className="login-perks">
              {role === 'artisan' ? (
                <>
                  <li><IconTruck size={14} /> Direct workshop listings stored in HunarLink MySQL / DB</li>
                  <li><IconBadgeCheck size={14} /> GI Registry &amp; Karigar verification workflow</li>
                  <li><IconShield size={14} /> Escrow-protected Razorpay payouts</li>
                </>
              ) : (
                <>
                  <li><IconTruck size={14} /> Live database-backed order tracking &amp; GI records</li>
                  <li><IconBookmark size={14} /> Saved addresses &amp; verified collector profile</li>
                  <li><IconShield size={14} /> Zero guest leakage — protected marketplace access</li>
                </>
              )}
            </ul>
          </div>

          <div className="login-right">
            {signedIn ? (
              <div style={{ padding: '1rem 0' }}>
                <div className="login-head">
                  <h2 className="login-title">You are signed in</h2>
                  <p className="login-sub">
                    Authenticated via Clerk as{' '}
                    <strong>{user?.name || user?.email || 'Verified Member'}</strong>
                    {user?.email ? ` (${user.email})` : ''}.
                  </p>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', marginTop: '1.25rem' }}>
                  <button
                    type="button"
                    className="btn-orange"
                    style={{ width: '100%', justifyContent: 'center' }}
                    onClick={() =>
                      navigate(
                        isArtisanSession
                          ? isVerifiedArtisan
                            ? '/seller'
                            : '/auth?tab=verify'
                          : nextUrl || '/'
                      )
                    }
                  >
                    <IconArrowRight size={15} />
                    {isArtisanSession
                      ? isVerifiedArtisan
                        ? 'Open Artisan Workspace'
                        : 'Complete Artisan Verification First'
                      : 'Enter HunarLink Marketplace'}
                  </button>
                  <button
                    type="button"
                    className="btn-orange-outline"
                    style={{ width: '100%', justifyContent: 'center' }}
                    onClick={signOutHere}
                  >
                    Sign out and switch account
                  </button>
                </div>
              </div>
            ) : (
              <>
                <div className="login-head">
                  <h2 className="login-title" id="login-title">
                    {authMode === 'register'
                      ? role === 'artisan'
                        ? 'Register New Artisan'
                        : 'Create HunarLink Account'
                      : role === 'artisan'
                        ? 'Artisan Sign In'
                        : 'Sign in to HunarLink'}
                  </h2>
                  <p className="login-sub" id="login-sub">
                    {authMode === 'register'
                      ? 'New to HunarLink? Existing database accounts cannot re-register — use Sign In instead.'
                      : role === 'artisan'
                        ? 'Existing artisans sign in below. Unverified artisans will land on the Verification page first.'
                        : 'Sign in with Google, Apple, or a verified email code to access your account.'}
                  </p>
                </div>

                <div className="seg" role="group" aria-labelledby="mode-label" style={{ marginBottom: '0.75rem' }}>
                  <span className="seg-label" id="mode-label">Action</span>
                  <div className="seg-track">
                    <button
                      type="button"
                      className={`seg-btn${authMode === 'signin' ? ' is-on' : ''}`}
                      aria-pressed={authMode === 'signin'}
                      onClick={() => {
                        setAuthMode('signin');
                        setSignInMethod('password');
                        setForgotStep('request');
                        setEmailStep('input');
                        setCode('');
                        setErrMsg('');
                        navigate(role === 'artisan' ? '/login?role=artisan' : '/login', { replace: true });
                      }}
                    >
                      Sign In
                    </button>
                    <button
                      type="button"
                      className={`seg-btn${authMode === 'register' ? ' is-on' : ''}`}
                      aria-pressed={authMode === 'register'}
                      onClick={() => {
                        setAuthMode('register');
                        setSignInMethod('password');
                        setForgotStep('request');
                        setEmailStep('input');
                        setCode('');
                        setErrMsg('');
                        navigate(role === 'artisan' ? '/register?role=artisan' : '/register', { replace: true });
                      }}
                    >
                      Register
                    </button>
                  </div>
                </div>

                <div className="seg" role="group" aria-labelledby="role-label">
                  <span className="seg-label" id="role-label">Account</span>
                  <div className="seg-track">
                    <button
                      type="button"
                      className={`seg-btn${role === 'user' ? ' is-on' : ''}`}
                      id="role-user"
                      aria-pressed={role === 'user'}
                      onClick={() => {
                        setRole('user');
                        setErrMsg('');
                        navigate(authMode === 'register' ? '/register' : '/login', { replace: true });
                      }}
                    >
                      <IconUser size={14} />
                      Buyer
                    </button>
                    <button
                      type="button"
                      className={`seg-btn${role === 'artisan' ? ' is-on' : ''}`}
                      id="role-artisan"
                      aria-pressed={role === 'artisan'}
                      onClick={() => {
                        setRole('artisan');
                        setErrMsg('');
                        navigate(
                          authMode === 'register' ? '/register?role=artisan' : '/login?role=artisan',
                          { replace: true }
                        );
                      }}
                    >
                      <IconSpark size={14} />
                      Artisan
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
                        onClick={() => startOAuth('google')}
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
                        onClick={() => startOAuth('apple')}
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

                    <div className="login-social-divider" aria-hidden="true">
                      <span>
                        {authMode === 'register'
                          ? 'or register with email & password'
                          : signInMethod === 'forgot'
                            ? 'reset your password'
                            : signInMethod === 'password'
                              ? 'or sign in with email & password'
                              : 'or sign in with email verification code'}
                      </span>
                    </div>

                    {emailStep === 'input' ? (
                      authMode === 'signin' && signInMethod === 'forgot' ? (
                        forgotStep === 'request' ? (
                          <form onSubmit={handleSendPasswordResetCode}>
                            <div className="form-field">
                              <label className="up-label" htmlFor="clerk-forgot-email-input">
                                Account Email Address *
                              </label>
                              <input
                                id="clerk-forgot-email-input"
                                type="email"
                                className="up-input"
                                placeholder="name@example.com"
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
                              <label className="up-label" htmlFor="clerk-reset-code-input">
                                6-Digit Reset Code sent to {email} *
                              </label>
                              <input
                                id="clerk-reset-code-input"
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
                              <label className="up-label" htmlFor="clerk-reset-new-password-input">
                                New Password (min. 15 characters) *
                              </label>
                              <input
                                id="clerk-reset-new-password-input"
                                type="password"
                                className="up-input"
                                placeholder="Create a new strong password (15+ characters)"
                                required
                                minLength={15}
                                autoComplete="new-password"
                                value={newPassword}
                                onChange={(e) => setNewPassword(e.target.value)}
                              />
                              <div
                                style={{
                                  fontSize: '0.74rem',
                                  marginTop: '0.28rem',
                                  opacity: 0.78,
                                  color:
                                    newPassword.length > 0 && newPassword.length < 15
                                      ? '#b33818'
                                      : 'inherit'
                                }}
                              >
                                {newPassword.length > 0
                                  ? `${newPassword.length}/15+ characters`
                                  : 'Minimum 15 characters required by security policy.'}
                              </div>
                            </div>
                            <div className="form-field">
                              <label className="up-label" htmlFor="clerk-reset-confirm-password-input">
                                Confirm New Password *
                              </label>
                              <input
                                id="clerk-reset-confirm-password-input"
                                type="password"
                                className="up-input"
                                placeholder="Re-enter your new password"
                                required
                                minLength={15}
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
                            <label className="up-label" htmlFor="clerk-email-input">
                              Email Address *
                            </label>
                            <input
                              id="clerk-email-input"
                              type="email"
                              className="up-input"
                              placeholder="name@example.com"
                              required
                              autoComplete="email"
                              value={email}
                              onChange={(e) => setEmail(e.target.value)}
                            />
                          </div>
                          <div className="form-field">
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '0.5rem' }}>
                              <label className="up-label" htmlFor="clerk-password-input" style={{ marginBottom: 0 }}>
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
                              id="clerk-password-input"
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
                            {emailBusy ? 'Signing in…' : 'Sign In with Password'}
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
                            <label className="up-label" htmlFor="clerk-email-input">
                              Email Address *
                            </label>
                            <input
                              id="clerk-email-input"
                              type="email"
                              className="up-input"
                              placeholder="name@example.com"
                              required
                              autoComplete="email"
                              value={email}
                              onChange={(e) => setEmail(e.target.value)}
                            />
                          </div>
                          {authMode === 'register' && (
                            <div className="form-field">
                              <label className="up-label" htmlFor="clerk-reg-password-input">
                                Create Password (min. 15 characters) *
                              </label>
                              <input
                                id="clerk-reg-password-input"
                                type="password"
                                className="up-input"
                                placeholder="Create a strong password (15+ characters)"
                                required
                                minLength={15}
                                autoComplete="new-password"
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                              />
                              <div
                                style={{
                                  fontSize: '0.74rem',
                                  marginTop: '0.28rem',
                                  opacity: 0.78,
                                  color:
                                    password.length > 0 && password.length < 15
                                      ? '#b33818'
                                      : 'inherit'
                                }}
                              >
                                {password.length > 0
                                  ? `${password.length}/15+ characters`
                                  : 'Minimum 15 characters required by security policy.'}
                              </div>
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
                          <label className="up-label" htmlFor="clerk-code-input">
                            6-Digit Code sent to {email} *
                          </label>
                          <input
                            id="clerk-code-input"
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
                        {pendingFlow === 'signUp' && password.length < 15 && (
                          <div className="form-field">
                            <label className="up-label" htmlFor="clerk-verify-password-input">
                              Create Password (min. 15 characters) *
                            </label>
                            <input
                              id="clerk-verify-password-input"
                              type="password"
                              className="up-input"
                              placeholder="Create a strong password (15+ characters)"
                              required
                              minLength={15}
                              autoComplete="new-password"
                              value={password}
                              onChange={(e) => setPassword(e.target.value)}
                            />
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
                              ? 'Verify & Complete Registration'
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
                  </div>
                ) : (
                  <div className="login-error show" role="alert">
                    Clerk authentication is required. Set <code>VITE_CLERK_PUBLISHABLE_KEY</code> in{' '}
                    <code>app/.env.local</code> and restart Vite.
                  </div>
                )}

                {role === 'artisan' && (
                  <p className="login-footer-note" style={{ marginTop: '1rem' }}>
                    {authMode === 'register'
                      ? 'Already registered as an artisan? Switch to Sign In above — existing accounts cannot re-register.'
                      : 'Artisans who have not yet been verified will automatically land on the Verification page first.'}
                  </p>
                )}
              </>
            )}
          </div>
        </section>
      </main>
    </div>
  );
}
