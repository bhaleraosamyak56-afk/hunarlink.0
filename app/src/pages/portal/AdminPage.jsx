import React, { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import '../../styles/portal.css';
import PortalScope from '../../components/PortalScope.jsx';
import { useStore } from '../../state/StoreContext.jsx';
import {
  canAttemptBackend,
  decideAdminArtisanApplication,
  decideAdminGuardrailCase,
  fetchAdminGuardrailCases,
  fetchAdminGuardrailRules,
  fetchAdminOverview,
  fetchAdminPayments,
  fetchAdminPaymentWebhooks,
  fetchAdminRefunds,
  fetchGuardrailDocumentBlobUrl,
  fetchMyAuthProfile,
  initiateAdminRefund,
  moderateAdminListing,
  verifyAdminSeller
} from '../../services/apiClient.js';
import { generateIdempotencyKey } from '../../services/razorpayCheckout.js';
import AdminLoginPage from './AdminLoginPage.jsx';
import AdminCraftProofTab from '../../components/craftproof/AdminCraftProofTab.jsx';
import {
  IconGrid,
  IconUsers,
  IconPalette,
  IconPackage,
  IconReceipt,
  IconShield,
  IconLogout
} from '../../components/LineIcons.jsx';

/* ==========================================================================
   AdminPage — Dedicated DB-Verified Email + Password Administrator Console
   --------------------------------------------------------------------------
   Uses an isolated signed HS256 Admin Session JWT issued ONLY by
   `POST /api/v1/auth/admin-login` for accounts explicitly provisioned in the
   database `admin_credentials` table. Re-validated live on every request.
   ========================================================================== */

const ADMIN_TOKEN_KEY = 'hunarlink_admin_session_jwt';

const TABS = [
  { id: 'overview', label: 'Overview & Users', icon: <IconGrid size={15} /> },
  { id: 'applications', label: 'Pending Artisan Verifications', icon: <IconShield size={15} /> },
  { id: 'sellers', label: 'Artisans & Listings', icon: <IconPalette size={15} /> },
  { id: 'admins', label: 'Admin DB Accounts', icon: <IconShield size={15} /> },
  { id: 'orders', label: 'Retail Orders', icon: <IconPackage size={15} /> },
  { id: 'payments', label: 'Payments & Refunds', icon: <IconReceipt size={15} /> },
  { id: 'guardrails', label: 'ASIGS Guardrails', icon: <IconShield size={15} /> },
  { id: 'craftproof', label: 'CraftProof Claims', icon: <IconShield size={15} /> }
];

const inr = (n) =>
  '₹' + Number(n || 0).toLocaleString('en-IN', { maximumFractionDigits: 2 });

function readStoredAdminToken() {
  try {
    return window.sessionStorage.getItem(ADMIN_TOKEN_KEY) || '';
  } catch {
    return '';
  }
}

function writeStoredAdminToken(token) {
  try {
    if (token) window.sessionStorage.setItem(ADMIN_TOKEN_KEY, token);
    else window.sessionStorage.removeItem(ADMIN_TOKEN_KEY);
  } catch {
    // ignore storage restriction
  }
}

export default function AdminPage() {
  const navigate = useNavigate();
  const { toast } = useStore();

  const [adminToken, setAdminToken] = useState(() => readStoredAdminToken());
  const [authState, setAuthState] = useState(() => ({
    status: readStoredAdminToken() ? 'checking' : 'unauthenticated',
    email: null,
    notice: null,
    profile: null
  }));
  const [tab, setTab] = useState('overview');
  const [loading, setLoading] = useState(false);
  const [revealedHashes, setRevealedHashes] = useState({});
  const [cardPreviewModal, setCardPreviewModal] = useState(null);
  const [busyAppId, setBusyAppId] = useState(null);
  const [data, setData] = useState({
    overview: null,
    payments: [],
    refunds: [],
    webhooks: [],
    cases: [],
    rules: []
  });

  const clearAdminSession = useCallback((notice = null) => {
    writeStoredAdminToken('');
    setAdminToken('');
    setData({
      overview: null,
      payments: [],
      refunds: [],
      webhooks: [],
      cases: [],
      rules: []
    });
    setAuthState({
      status: 'unauthenticated',
      email: null,
      notice,
      profile: null
    });
  }, []);

  const loadLiveAdminData = useCallback(
    async (explicitToken = null) => {
      const token = explicitToken ?? adminToken;
      if (!token) {
        setAuthState({ status: 'unauthenticated', email: null, notice: null, profile: null });
        return;
      }

      if (!canAttemptBackend()) {
        clearAdminSession('Live FastAPI backend is required to access the Admin Console.');
        return;
      }

      setAuthState((prev) => ({
        ...prev,
        status: prev.status === 'authorized' ? 'authorized' : 'checking',
        notice: null
      }));

      try {
        const me = await fetchMyAuthProfile(token);
        if (!me?.is_admin) {
          clearAdminSession(
            'This administrator session is no longer active or authorized in the database.'
          );
          return;
        }

        setAuthState({
          status: 'authorized',
          email: me.email,
          notice: null,
          profile: me
        });
        setLoading(true);

        const [overview, payments, refunds, webhooks, cases, rules] = await Promise.all([
          fetchAdminOverview(token),
          fetchAdminPayments(token).catch(() => []),
          fetchAdminRefunds(token).catch(() => []),
          fetchAdminPaymentWebhooks(token).catch(() => []),
          fetchAdminGuardrailCases(token).catch(() => []),
          fetchAdminGuardrailRules(token).catch(() => [])
        ]);

        setData({
          overview,
          payments: Array.isArray(payments) ? payments : [],
          refunds: Array.isArray(refunds) ? refunds : [],
          webhooks: Array.isArray(webhooks) ? webhooks : [],
          cases: Array.isArray(cases) ? cases : [],
          rules: Array.isArray(rules) ? rules : []
        });
      } catch (err) {
        clearAdminSession(
          err?.message || 'Administrator session expired or revoked. Please sign in again.'
        );
      } finally {
        setLoading(false);
      }
    },
    [adminToken, clearAdminSession]
  );

  useEffect(() => {
    if (adminToken) {
      loadLiveAdminData(adminToken);
    }
  }, [adminToken, loadLiveAdminData]);

  async function handleAdminAuthenticated(loginResponse) {
    const token = loginResponse?.access_token;
    if (!token) return;
    writeStoredAdminToken(token);
    setAdminToken(token);
    await loadLiveAdminData(token);
  }

  async function handleRefund(payment) {
    const reason = window.prompt(
      `Refund reason for ${payment.payment_reference || payment.id} (min 5 chars):`
    );
    if (!reason || reason.trim().length < 5) {
      if (reason !== null) toast('Refund reason must be at least 5 characters.', 'error');
      return;
    }
    try {
      await initiateAdminRefund(
        payment.id,
        {
          refund_type: 'FULL',
          reason: reason.trim(),
          idempotency_key: generateIdempotencyKey('refund')
        },
        adminToken
      );
      toast('Full refund submitted to Razorpay & recorded in database.', 'success');
      loadLiveAdminData(adminToken);
    } catch (err) {
      toast(err?.message || 'Refund failed.', 'error');
    }
  }

  async function handleCaseDecision(caseId, decision) {
    const reason = window.prompt(`Audit reason for ${decision} (min 5 chars):`);
    if (!reason || reason.trim().length < 5) {
      if (reason !== null) toast('Decision reason must be at least 5 characters.', 'error');
      return;
    }
    try {
      await decideAdminGuardrailCase(
        caseId,
        { decision, reason: reason.trim() },
        adminToken
      );
      toast(`Guardrail case marked ${decision}.`, 'success');
      loadLiveAdminData(adminToken);
    } catch (err) {
      toast(err?.message || 'Could not record decision.', 'error');
    }
  }

  async function handleModerateListing(listingId, nextStatus) {
    try {
      await moderateAdminListing(listingId, nextStatus, adminToken);
      toast(`Craft listing status updated to ${nextStatus}.`, 'success');
      loadLiveAdminData(adminToken);
    } catch (err) {
      toast(err?.message || 'Could not update listing status.', 'error');
    }
  }

  async function handleViewArtisanCard(appItem) {
    if (!appItem?.artisan_card_scan_id) {
      toast('No Artisan Card file is attached to this application.', 'error');
      return;
    }
    try {
      const { blobUrl, mimeType } = await fetchGuardrailDocumentBlobUrl(
        appItem.artisan_card_scan_id,
        adminToken
      );
      if (cardPreviewModal?.blobUrl) {
        URL.revokeObjectURL(cardPreviewModal.blobUrl);
      }
      setCardPreviewModal({
        blobUrl,
        mimeType,
        appNumber: appItem.application_number,
        storeName: appItem.store_name,
        artisanName: appItem.artisan_name,
        filename: appItem.artisan_card_filename || 'artisan-card',
        applicationId: appItem.id,
        status: appItem.application_status
      });
    } catch (err) {
      toast(err?.message || 'Could not retrieve Artisan Card from private DB storage.', 'error');
    }
  }

  function closeCardPreviewModal() {
    if (cardPreviewModal?.blobUrl) {
      URL.revokeObjectURL(cardPreviewModal.blobUrl);
    }
    setCardPreviewModal(null);
  }

  async function handleDecideArtisanApplication(appItem, decision) {
    let notes = '';
    if (decision === 'REJECT') {
      const entered = window.prompt(
        `Reason for rejecting ${appItem.store_name} (${appItem.application_number}):`,
        'Artisan card image was unclear — please re-upload a clear photo.'
      );
      if (entered === null) return;
      notes = entered.trim();
    } else {
      notes = 'Artisan Card / GI details verified by Admin and promoted to live directory.';
    }

    setBusyAppId(appItem.id);
    try {
      const res = await decideAdminArtisanApplication(
        appItem.id,
        { decision, notes },
        adminToken
      );
      if (cardPreviewModal?.applicationId === appItem.id) {
        closeCardPreviewModal();
      }
      toast(
        decision === 'APPROVE'
          ? `Approved ${res.store_name}! Promoted live to /artisan?id=${res.seller_profile_id}`
          : `Application ${res.application_number} marked REJECTED.`,
        'success'
      );
      await loadLiveAdminData(adminToken);
    } catch (err) {
      toast(err?.message || 'Could not update artisan application.', 'error');
    } finally {
      setBusyAppId(null);
    }
  }

  async function handleVerifySeller(sellerId, decision) {
    try {
      await verifyAdminSeller(sellerId, decision, adminToken);
      toast(`Artisan verification marked ${decision}.`, 'success');
      loadLiveAdminData(adminToken);
    } catch (err) {
      toast(err?.message || 'Could not update artisan verification.', 'error');
    }
  }

  if (authState.status === 'checking') {
    return <AdminLoginPage checking />;
  }
  if (authState.status !== 'authorized') {
    return (
      <AdminLoginPage
        onAuthenticated={handleAdminAuthenticated}
        sessionNotice={authState.notice}
      />
    );
  }

  const ov = data.overview || {
    counts: {},
    artisan_applications: [],
    admin_credentials: [],
    users: [],
    sellers: [],
    listings: [],
    orders: []
  };

  return (
    <>
      <PortalScope family="admin" />
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
              <div className="up-brand-title">HunarLink Admin</div>
              <div className="up-brand-sub">Live Database &amp; RBAC Console</div>
            </div>
          </Link>
          <nav className="up-nav-links">
            <span style={{ fontSize: '0.82rem', opacity: 0.78 }}>{authState.email}</span>
            <Link to="/" className="up-nav-pill">Storefront</Link>
            <button
              type="button"
              className="up-nav-pill up-nav-signout"
              onClick={() => {
                clearAdminSession(null);
                navigate('/', { replace: true });
              }}
            >
              <IconLogout size={14} /> Sign out
            </button>
          </nav>
        </div>
      </header>

      <main className="up-container" id="main-content" style={{ paddingBlock: '1.75rem 3.5rem' }}>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', marginBottom: '1.5rem' }}>
          {TABS.map((t) => {
            const pendingCount =
              t.id === 'applications' ? Number(ov.counts?.pending_applications || 0) : 0;
            return (
              <button
                key={t.id}
                type="button"
                className={tab === t.id ? 'btn-orange' : 'btn-orange-outline'}
                onClick={() => setTab(t.id)}
              >
                {t.icon} {t.label}
                {pendingCount > 0 ? ` (${pendingCount})` : ''}
              </button>
            );
          })}
          <button
            type="button"
            className="btn-orange-outline"
            style={{ marginLeft: 'auto' }}
            onClick={() => loadLiveAdminData(adminToken)}
            disabled={loading}
          >
            {loading ? 'Refreshing…' : 'Refresh Live DB'}
          </button>
        </div>

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))',
            gap: '1rem',
            marginBottom: '1.5rem'
          }}
        >
          <div className="fk-panel-card" style={{ padding: '1rem 1.25rem' }}>
            <div style={{ fontSize: '0.78rem', opacity: 0.7 }}>AUTHORIZED ADMINS</div>
            <div style={{ fontSize: '1.75rem', fontWeight: 700 }}>{ov.counts?.admins ?? 0}</div>
          </div>
          <div className="fk-panel-card" style={{ padding: '1rem 1.25rem' }}>
            <div style={{ fontSize: '0.78rem', opacity: 0.7 }}>USERS IN DB</div>
            <div style={{ fontSize: '1.75rem', fontWeight: 700 }}>{ov.counts?.users ?? 0}</div>
          </div>
          <div
            className="fk-panel-card"
            style={{
              padding: '1rem 1.25rem',
              cursor: 'pointer',
              border:
                (ov.counts?.pending_applications ?? 0) > 0
                  ? '1px solid rgba(199, 91, 57, 0.45)'
                  : undefined
            }}
            onClick={() => setTab('applications')}
          >
            <div style={{ fontSize: '0.78rem', opacity: 0.7 }}>PENDING ARTISAN CARDS</div>
            <div style={{ fontSize: '1.75rem', fontWeight: 700, color: '#a34121' }}>
              {ov.counts?.pending_applications ?? 0}
            </div>
          </div>
          <div className="fk-panel-card" style={{ padding: '1rem 1.25rem' }}>
            <div style={{ fontSize: '0.78rem', opacity: 0.7 }}>ARTISAN PROFILES</div>
            <div style={{ fontSize: '1.75rem', fontWeight: 700 }}>{ov.counts?.sellers ?? 0}</div>
          </div>
          <div className="fk-panel-card" style={{ padding: '1rem 1.25rem' }}>
            <div style={{ fontSize: '0.78rem', opacity: 0.7 }}>ACTIVE LISTINGS</div>
            <div style={{ fontSize: '1.75rem', fontWeight: 700 }}>{ov.counts?.listings ?? 0}</div>
          </div>
          <div className="fk-panel-card" style={{ padding: '1rem 1.25rem' }}>
            <div style={{ fontSize: '0.78rem', opacity: 0.7 }}>RETAIL ORDERS</div>
            <div style={{ fontSize: '1.75rem', fontWeight: 700 }}>{ov.counts?.orders ?? 0}</div>
          </div>
        </div>

        {tab === 'overview' && (
          <section className="fk-panel-card" style={{ padding: '1.25rem' }}>
            <h2 style={{ marginBottom: '0.9rem', display: 'flex', alignItems: 'center', gap: '0.45rem' }}>
              <IconUsers size={18} /> Registered Users (Live DB)
            </h2>
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.88rem' }}>
                <thead>
                  <tr style={{ textAlign: 'left', borderBottom: '1px solid rgba(0,0,0,0.1)' }}>
                    <th style={{ padding: '0.55rem' }}>Name</th>
                    <th style={{ padding: '0.55rem' }}>Email</th>
                    <th style={{ padding: '0.55rem' }}>Identity ID</th>
                    <th style={{ padding: '0.55rem' }}>Onboarding Stage</th>
                    <th style={{ padding: '0.55rem' }}>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {(ov.users || []).map((u) => (
                    <tr key={u.id} style={{ borderBottom: '1px solid rgba(0,0,0,0.06)' }}>
                      <td style={{ padding: '0.55rem', fontWeight: 600 }}>{u.name}</td>
                      <td style={{ padding: '0.55rem' }}>{u.email}</td>
                      <td style={{ padding: '0.55rem', fontFamily: 'monospace', fontSize: '0.78rem' }}>{u.clerk_user_id}</td>
                      <td style={{ padding: '0.55rem', fontSize: '0.78rem' }}>
                        {u.onboarding_state === 'ADMIN' ? (
                          <span
                            style={{
                              display: 'inline-block',
                              padding: '0.16rem 0.52rem',
                              borderRadius: '999px',
                              background: 'rgba(20, 62, 48, 0.12)',
                              color: '#143e30',
                              fontWeight: 700,
                              letterSpacing: '0.03em'
                            }}
                          >
                            ADMIN
                          </span>
                        ) : u.onboarding_state === 'STEP_1_ONLY_NO_CARD_YET' ? (
                          <span style={{ color: '#8a5300', fontWeight: 600 }}>
                            Step 1 Signed In (Awaiting Card Upload on /auth?tab=verify)
                          </span>
                        ) : u.onboarding_state === 'SUBMITTED' ? (
                          <span style={{ color: '#a34121', fontWeight: 600 }}>
                            Pending Admin Review
                          </span>
                        ) : u.onboarding_state === 'APPROVED' ? (
                          <span style={{ color: '#1b6d3f', fontWeight: 600 }}>
                            Verified Artisan
                          </span>
                        ) : (
                          <span style={{ opacity: 0.7 }}>{u.onboarding_state || 'BUYER'}</span>
                        )}
                      </td>
                      <td style={{ padding: '0.55rem' }}>{u.account_status}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        )}

        {tab === 'applications' && (
          <section className="fk-panel-card" style={{ padding: '1.25rem' }}>
            <h2 style={{ marginBottom: '0.4rem', display: 'flex', alignItems: 'center', gap: '0.45rem' }}>
              <IconShield size={18} /> Artisan Verification Queue (<code>seller_verification_applications</code>)
            </h2>
            <p style={{ fontSize: '0.85rem', opacity: 0.78, marginBottom: '1.1rem' }}>
              Every Standard Artisan (with Artisan Card image) or GI Certified registration stays staged
              in the database as <code>SUBMITTED / DRAFT</code> until verified here. Clicking{' '}
              <strong>Verify &amp; Push Live</strong> promotes their <code>seller_profiles</code> record to{' '}
              <code>APPROVED / ACTIVE</code> and publishes their unique workshop URL (<code>/artisan?id=&lt;uuid&gt;</code>).
            </p>
            {(ov.incomplete_artisan_signups || []).length > 0 && (
              <div
                style={{
                  marginBottom: '1rem',
                  padding: '0.8rem 1rem',
                  borderRadius: '10px',
                  background: 'rgba(138, 83, 0, 0.08)',
                  border: '1px solid rgba(138, 83, 0, 0.25)',
                  fontSize: '0.82rem'
                }}
              >
                <div style={{ fontWeight: 700, color: '#7a4900', marginBottom: '0.3rem' }}>
                  Step 1 Signed-In Artisans Awaiting Step 2 Card Submission ({ov.incomplete_artisan_signups.length})
                </div>
                <div style={{ opacity: 0.85, marginBottom: '0.45rem' }}>
                  These accounts completed Step 1 login on <code>/login</code>, so they appear in{' '}
                  <code>users</code>, and will appear in this verification queue as soon as they submit their
                  Workshop &amp; Artisan Card on <code>/auth?tab=verify</code>:
                </div>
                <ul style={{ margin: 0, paddingLeft: '1.2rem' }}>
                  {ov.incomplete_artisan_signups.map((inc) => (
                    <li key={inc.user_id}>
                      <strong>{inc.name}</strong> ({inc.email})
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {(ov.artisan_applications || []).length === 0 ? (
              <p style={{ opacity: 0.7 }}>No artisan verification applications in the database yet.</p>
            ) : (
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.86rem' }}>
                  <thead>
                    <tr style={{ textAlign: 'left', borderBottom: '1px solid rgba(0,0,0,0.1)' }}>
                      <th style={{ padding: '0.55rem' }}>App #</th>
                      <th style={{ padding: '0.55rem' }}>Workshop &amp; Artisan</th>
                      <th style={{ padding: '0.55rem' }}>Craft &amp; District</th>
                      <th style={{ padding: '0.55rem' }}>Track / GI</th>
                      <th style={{ padding: '0.55rem' }}>Artisan Card</th>
                      <th style={{ padding: '0.55rem' }}>DB Status</th>
                      <th style={{ padding: '0.55rem' }}>Admin Verification</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(ov.artisan_applications || []).map((appItem) => {
                      const isPending = ['SUBMITTED', 'UNDER_REVIEW', 'NEEDS_MORE_INFO'].includes(
                        appItem.application_status
                      );
                      return (
                        <tr
                          key={appItem.id}
                          style={{
                            borderBottom: '1px solid rgba(0,0,0,0.06)',
                            background: isPending ? 'rgba(199, 91, 57, 0.05)' : undefined
                          }}
                        >
                          <td style={{ padding: '0.55rem', fontFamily: 'monospace', fontSize: '0.78rem' }}>
                            <div>{appItem.application_number}</div>
                            <div style={{ fontSize: '0.7rem', opacity: 0.65 }}>
                              {appItem.seller_profile_id?.slice(0, 8)}…
                            </div>
                          </td>
                          <td style={{ padding: '0.55rem' }}>
                            <div style={{ fontWeight: 600 }}>{appItem.store_name}</div>
                            <div style={{ fontSize: '0.78rem', opacity: 0.78 }}>
                              {appItem.artisan_name}
                              {appItem.artisan_email ? ` • ${appItem.artisan_email}` : ''}
                              {appItem.artisan_phone ? ` • ${appItem.artisan_phone}` : ''}
                            </div>
                          </td>
                          <td style={{ padding: '0.55rem' }}>
                            <div>{appItem.craft_specialty || '—'}</div>
                            <div style={{ fontSize: '0.78rem', opacity: 0.75 }}>
                              {appItem.workshop_district || '—'}
                            </div>
                          </td>
                          <td style={{ padding: '0.55rem' }}>
                            <span style={{ fontWeight: 600 }}>
                              {appItem.verification_path === 'GI' ? 'GI Certified' : 'Standard Artisan'}
                            </span>
                            {appItem.claimed_gi_code && (
                              <div style={{ fontFamily: 'monospace', fontSize: '0.75rem' }}>
                                {appItem.claimed_gi_code}
                              </div>
                            )}
                          </td>
                          <td style={{ padding: '0.55rem' }}>
                            {appItem.artisan_card_scan_id ? (
                              <button
                                type="button"
                                className="btn-orange-outline"
                                style={{ padding: '0.25rem 0.6rem', fontSize: '0.75rem' }}
                                onClick={() => handleViewArtisanCard(appItem)}
                              >
                                View Artisan Card
                              </button>
                            ) : (
                              <span style={{ fontSize: '0.76rem', opacity: 0.6 }}>No card file</span>
                            )}
                          </td>
                          <td style={{ padding: '0.55rem', fontWeight: 600 }}>
                            <div>{appItem.application_status}</div>
                            {appItem.application_status === 'APPROVED' && (
                              <Link
                                to={`/artisan?id=${encodeURIComponent(appItem.seller_profile_id)}`}
                                style={{ fontSize: '0.74rem', color: '#a34121', textDecoration: 'underline' }}
                              >
                                Open Live Profile →
                              </Link>
                            )}
                          </td>
                          <td style={{ padding: '0.55rem' }}>
                            <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap' }}>
                              {appItem.application_status !== 'APPROVED' && (
                                <button
                                  type="button"
                                  className="btn-orange"
                                  style={{ padding: '0.28rem 0.65rem', fontSize: '0.75rem' }}
                                  disabled={busyAppId === appItem.id}
                                  onClick={() => handleDecideArtisanApplication(appItem, 'APPROVE')}
                                >
                                  Verify &amp; Push Live
                                </button>
                              )}
                              {appItem.application_status !== 'REJECTED' && (
                                <button
                                  type="button"
                                  className="btn-orange-outline"
                                  style={{ padding: '0.28rem 0.65rem', fontSize: '0.75rem' }}
                                  disabled={busyAppId === appItem.id}
                                  onClick={() => handleDecideArtisanApplication(appItem, 'REJECT')}
                                >
                                  Reject
                                </button>
                              )}
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        )}

        {tab === 'admins' && (
          <section className="fk-panel-card" style={{ padding: '1.25rem' }}>
            <h2 style={{ marginBottom: '0.45rem', display: 'flex', alignItems: 'center', gap: '0.45rem' }}>
              <IconShield size={18} /> Authorized Admin Accounts (<code>admin_credentials</code> Table)
            </h2>
            <p style={{ fontSize: '0.85rem', opacity: 0.78, marginBottom: '1rem' }}>
              Only active accounts listed in the <code>admin_credentials</code> database table can
              sign in at <code>/admin</code>. Passwords are stored securely as salted{' '}
              <code>PBKDF2-HMAC-SHA256</code> hashes (390,000 iterations) &mdash; never plaintext.
            </p>
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.86rem' }}>
                <thead>
                  <tr style={{ textAlign: 'left', borderBottom: '1px solid rgba(0,0,0,0.1)' }}>
                    <th style={{ padding: '0.55rem' }}>Admin Name</th>
                    <th style={{ padding: '0.55rem' }}>Authorized Email</th>
                    <th style={{ padding: '0.55rem' }}>Stored Password Credential (DB Hash)</th>
                    <th style={{ padding: '0.55rem' }}>Status</th>
                    <th style={{ padding: '0.55rem' }}>Last Login</th>
                  </tr>
                </thead>
                <tbody>
                  {(ov.admin_credentials || []).map((a) => {
                    const shown = Boolean(revealedHashes[a.id]);
                    const maskedHash = a.password_hash
                      ? `${a.password_hash.slice(0, 22)}••••••••••••`
                      : '—';
                    return (
                      <tr key={a.id} style={{ borderBottom: '1px solid rgba(0,0,0,0.06)' }}>
                        <td style={{ padding: '0.55rem', fontWeight: 600 }}>{a.name}</td>
                        <td style={{ padding: '0.55rem', fontWeight: 600 }}>{a.email}</td>
                        <td style={{ padding: '0.55rem', fontFamily: 'monospace', fontSize: '0.76rem' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
                            <span style={{ wordBreak: 'break-all' }}>
                              {shown ? a.password_hash : maskedHash}
                            </span>
                            <button
                              type="button"
                              className="btn-orange-outline"
                              style={{ padding: '0.2rem 0.5rem', fontSize: '0.72rem' }}
                              onClick={() =>
                                setRevealedHashes((prev) => ({ ...prev, [a.id]: !prev[a.id] }))
                              }
                            >
                              {shown ? 'Hide Hash' : 'Show DB Hash'}
                            </button>
                          </div>
                        </td>
                        <td style={{ padding: '0.55rem', fontWeight: 600 }}>
                          {a.is_active ? 'ACTIVE' : 'REVOKED'}
                        </td>
                        <td style={{ padding: '0.55rem', fontSize: '0.8rem' }}>
                          {a.last_login_at ? new Date(a.last_login_at).toLocaleString() : 'Never'}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <p style={{ fontSize: '0.8rem', opacity: 0.72, marginTop: '1rem' }}>
              Provision, rotate passwords, or revoke accounts directly on your database server with:{' '}
              <code>python backend/scripts/create_admin_account.py --email &quot;...&quot; --password &quot;...&quot; --name &quot;...&quot;</code>
            </p>
          </section>
        )}

        {tab === 'sellers' && (
          <section className="fk-panel-card" style={{ padding: '1.25rem' }}>
            <h2 style={{ marginBottom: '0.9rem' }}>Artisan Profiles &amp; Listings (Live DB)</h2>
            <div style={{ overflowX: 'auto', marginBottom: '1.5rem' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.88rem' }}>
                <thead>
                  <tr style={{ textAlign: 'left', borderBottom: '1px solid rgba(0,0,0,0.1)' }}>
                    <th style={{ padding: '0.55rem' }}>Workshop</th>
                    <th style={{ padding: '0.55rem' }}>District</th>
                    <th style={{ padding: '0.55rem' }}>Path / GI</th>
                    <th style={{ padding: '0.55rem' }}>Status</th>
                    <th style={{ padding: '0.55rem' }}>Verification</th>
                  </tr>
                </thead>
                <tbody>
                  {(ov.sellers || []).map((s) => (
                    <tr key={s.id} style={{ borderBottom: '1px solid rgba(0,0,0,0.06)' }}>
                      <td style={{ padding: '0.55rem', fontWeight: 600 }}>{s.store_name}</td>
                      <td style={{ padding: '0.55rem' }}>{s.workshop_district || '—'}</td>
                      <td style={{ padding: '0.55rem' }}>{s.verification_path} {s.claimed_gi_code ? `(${s.claimed_gi_code})` : ''}</td>
                      <td style={{ padding: '0.55rem' }}>{s.verification_status} / {s.profile_status}</td>
                      <td style={{ padding: '0.55rem' }}>
                        <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap' }}>
                          {s.verification_status !== 'APPROVED' && (
                            <button
                              type="button"
                              className="btn-orange"
                              style={{ padding: '0.25rem 0.6rem', fontSize: '0.75rem' }}
                              onClick={() => handleVerifySeller(s.id, 'APPROVED')}
                            >
                              Approve Artisan
                            </button>
                          )}
                          {s.verification_status !== 'REJECTED' && (
                            <button
                              type="button"
                              className="btn-orange-outline"
                              style={{ padding: '0.25rem 0.6rem', fontSize: '0.75rem' }}
                              onClick={() => handleVerifySeller(s.id, 'REJECTED')}
                            >
                              Reject
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <h3 style={{ marginBottom: '0.65rem' }}>Craft Listings (Approve / Moderate Live DB)</h3>
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.88rem' }}>
                <thead>
                  <tr style={{ textAlign: 'left', borderBottom: '1px solid rgba(0,0,0,0.1)' }}>
                    <th style={{ padding: '0.55rem' }}>SKU</th>
                    <th style={{ padding: '0.55rem' }}>Title</th>
                    <th style={{ padding: '0.55rem' }}>Price</th>
                    <th style={{ padding: '0.55rem' }}>Status</th>
                    <th style={{ padding: '0.55rem' }}>Moderation</th>
                  </tr>
                </thead>
                <tbody>
                  {(ov.listings || []).map((l) => (
                    <tr key={l.id} style={{ borderBottom: '1px solid rgba(0,0,0,0.06)' }}>
                      <td style={{ padding: '0.55rem', fontFamily: 'monospace' }}>{l.sku}</td>
                      <td style={{ padding: '0.55rem' }}>{l.title}</td>
                      <td style={{ padding: '0.55rem' }}>{inr(l.price)}</td>
                      <td style={{ padding: '0.55rem', fontWeight: 600 }}>{l.status}</td>
                      <td style={{ padding: '0.55rem' }}>
                        <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap' }}>
                          {l.status !== 'ACTIVE' && (
                            <button
                              type="button"
                              className="btn-orange"
                              style={{ padding: '0.25rem 0.6rem', fontSize: '0.75rem' }}
                              onClick={() => handleModerateListing(l.id, 'ACTIVE')}
                            >
                              Approve Live
                            </button>
                          )}
                          {l.status === 'ACTIVE' && (
                            <button
                              type="button"
                              className="btn-orange-outline"
                              style={{ padding: '0.25rem 0.6rem', fontSize: '0.75rem' }}
                              onClick={() => handleModerateListing(l.id, 'PAUSED')}
                            >
                              Pause
                            </button>
                          )}
                          {l.status !== 'REJECTED' && (
                            <button
                              type="button"
                              className="btn-orange-outline"
                              style={{ padding: '0.25rem 0.6rem', fontSize: '0.75rem' }}
                              onClick={() => handleModerateListing(l.id, 'REJECTED')}
                            >
                              Reject
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        )}

        {tab === 'orders' && (
          <section className="fk-panel-card" style={{ padding: '1.25rem' }}>
            <h2 style={{ marginBottom: '0.9rem' }}>Retail Orders (Live DB)</h2>
            {(ov.orders || []).length === 0 ? (
              <p style={{ opacity: 0.7 }}>No retail orders placed in the database yet.</p>
            ) : (
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.88rem' }}>
                  <thead>
                    <tr style={{ textAlign: 'left', borderBottom: '1px solid rgba(0,0,0,0.1)' }}>
                      <th style={{ padding: '0.55rem' }}>Order #</th>
                      <th style={{ padding: '0.55rem' }}>Total</th>
                      <th style={{ padding: '0.55rem' }}>Method</th>
                      <th style={{ padding: '0.55rem' }}>Payment</th>
                      <th style={{ padding: '0.55rem' }}>Fulfilment</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(ov.orders || []).map((o) => (
                      <tr key={o.id} style={{ borderBottom: '1px solid rgba(0,0,0,0.06)' }}>
                        <td style={{ padding: '0.55rem', fontFamily: 'monospace' }}>{o.order_number}</td>
                        <td style={{ padding: '0.55rem' }}>{inr(o.total_amount)}</td>
                        <td style={{ padding: '0.55rem' }}>{o.payment_method}</td>
                        <td style={{ padding: '0.55rem' }}>{o.payment_status}</td>
                        <td style={{ padding: '0.55rem' }}>{o.fulfilment_status}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        )}

        {tab === 'payments' && (
          <section className="fk-panel-card" style={{ padding: '1.25rem' }}>
            <h2 style={{ marginBottom: '0.9rem' }}>Razorpay Payments &amp; Refunds (Live DB)</h2>
            {data.payments.length === 0 ? (
              <p style={{ opacity: 0.7, marginBottom: '1.25rem' }}>
                No Razorpay payment records in the database yet.
              </p>
            ) : (
              <div style={{ overflowX: 'auto', marginBottom: '1.5rem' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.86rem' }}>
                  <thead>
                    <tr style={{ textAlign: 'left', borderBottom: '1px solid rgba(0,0,0,0.1)' }}>
                      <th style={{ padding: '0.55rem' }}>Reference</th>
                      <th style={{ padding: '0.55rem' }}>Provider Payment</th>
                      <th style={{ padding: '0.55rem' }}>Amount / Captured</th>
                      <th style={{ padding: '0.55rem' }}>Refunded</th>
                      <th style={{ padding: '0.55rem' }}>Status</th>
                      <th style={{ padding: '0.55rem' }}>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.payments.map((p) => {
                      const pStatus = p.payment_status || p.status || '—';
                      return (
                        <tr key={p.id} style={{ borderBottom: '1px solid rgba(0,0,0,0.06)' }}>
                          <td style={{ padding: '0.55rem', fontFamily: 'monospace', fontSize: '0.78rem' }}>
                            {p.payment_reference || p.id}
                          </td>
                          <td style={{ padding: '0.55rem', fontFamily: 'monospace', fontSize: '0.76rem' }}>
                            {p.provider_payment_id || p.provider_order_id || '—'}
                          </td>
                          <td style={{ padding: '0.55rem' }}>
                            {inr(p.amount)} / {inr(p.captured_amount)}
                          </td>
                          <td style={{ padding: '0.55rem' }}>{inr(p.refunded_amount)}</td>
                          <td style={{ padding: '0.55rem', fontWeight: 600 }}>{pStatus}</td>
                          <td style={{ padding: '0.55rem' }}>
                            {pStatus === 'CAPTURED' && (
                              <button
                                type="button"
                                className="btn-orange-outline"
                                style={{ padding: '0.3rem 0.65rem', fontSize: '0.78rem' }}
                                onClick={() => handleRefund(p)}
                              >
                                Full Refund
                              </button>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}

            <h3 style={{ marginBottom: '0.65rem' }}>Refund Ledger ({data.refunds.length})</h3>
            {data.refunds.length === 0 ? (
              <p style={{ opacity: 0.7, marginBottom: '1.25rem', fontSize: '0.86rem' }}>
                No refunds initiated yet.
              </p>
            ) : (
              <div style={{ overflowX: 'auto', marginBottom: '1.5rem' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
                  <thead>
                    <tr style={{ textAlign: 'left', borderBottom: '1px solid rgba(0,0,0,0.1)' }}>
                      <th style={{ padding: '0.5rem' }}>Refund Ref</th>
                      <th style={{ padding: '0.5rem' }}>Type</th>
                      <th style={{ padding: '0.5rem' }}>Amount</th>
                      <th style={{ padding: '0.5rem' }}>Status</th>
                      <th style={{ padding: '0.5rem' }}>Reason</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.refunds.map((r) => (
                      <tr key={r.id} style={{ borderBottom: '1px solid rgba(0,0,0,0.06)' }}>
                        <td style={{ padding: '0.5rem', fontFamily: 'monospace', fontSize: '0.76rem' }}>
                          {r.refund_reference}
                        </td>
                        <td style={{ padding: '0.5rem' }}>{r.refund_type}</td>
                        <td style={{ padding: '0.5rem' }}>{inr(r.amount)}</td>
                        <td style={{ padding: '0.5rem', fontWeight: 600 }}>{r.refund_status}</td>
                        <td style={{ padding: '0.5rem' }}>{r.reason}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            <h3 style={{ marginBottom: '0.65rem' }}>Razorpay Webhook Events ({data.webhooks.length})</h3>
            {data.webhooks.length === 0 ? (
              <p style={{ opacity: 0.7, fontSize: '0.86rem' }}>No webhook deliveries recorded yet.</p>
            ) : (
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.84rem' }}>
                  <thead>
                    <tr style={{ textAlign: 'left', borderBottom: '1px solid rgba(0,0,0,0.1)' }}>
                      <th style={{ padding: '0.5rem' }}>Event ID</th>
                      <th style={{ padding: '0.5rem' }}>Type</th>
                      <th style={{ padding: '0.5rem' }}>HMAC Verified</th>
                      <th style={{ padding: '0.5rem' }}>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.webhooks.map((w) => (
                      <tr key={w.id} style={{ borderBottom: '1px solid rgba(0,0,0,0.06)' }}>
                        <td style={{ padding: '0.5rem', fontFamily: 'monospace', fontSize: '0.76rem' }}>
                          {w.provider_event_id}
                        </td>
                        <td style={{ padding: '0.5rem' }}>{w.event_type}</td>
                        <td style={{ padding: '0.5rem' }}>{w.signature_verified ? 'YES' : 'NO'}</td>
                        <td style={{ padding: '0.5rem' }}>{w.processing_status}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        )}

        {tab === 'guardrails' && (
          <section className="fk-panel-card" style={{ padding: '1.25rem' }}>
            <h2 style={{ marginBottom: '0.9rem' }}>ASIGS Guardrail Review Queue (Live DB)</h2>
            {data.cases.length === 0 ? (
              <p style={{ opacity: 0.7, marginBottom: '1.5rem' }}>
                No guardrail cases pending review.
              </p>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', marginBottom: '1.5rem' }}>
                {data.cases.map((c) => (
                  <div
                    key={c.id}
                    style={{
                      border: '1px solid rgba(0,0,0,0.1)',
                      borderRadius: '10px',
                      padding: '0.9rem',
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      gap: '1rem',
                      flexWrap: 'wrap'
                    }}
                  >
                    <div>
                      <div>
                        <strong>{c.case_number}</strong> &middot; {c.workflow_name} ({c.target_type})
                      </div>
                      <div style={{ fontSize: '0.82rem', opacity: 0.78, marginTop: '0.2rem' }}>
                        Outcome: <strong>{c.guardrail_outcome}</strong> &middot; Case:{' '}
                        <strong>{c.case_status}</strong>
                        {Array.isArray(c.reason_codes) && c.reason_codes.length > 0 && (
                          <> &middot; Rules: <code>{c.reason_codes.join(', ')}</code></>
                        )}
                      </div>
                      {c.decision_reason && (
                        <div style={{ fontSize: '0.8rem', opacity: 0.72, marginTop: '0.2rem' }}>
                          Decision note: {c.decision_reason}
                        </div>
                      )}
                    </div>
                    {c.case_status === 'OPEN' && (
                      <div style={{ display: 'flex', gap: '0.5rem' }}>
                        <button
                          type="button"
                          className="btn-orange"
                          style={{ padding: '0.35rem 0.7rem', fontSize: '0.78rem' }}
                          onClick={() => handleCaseDecision(c.id, 'APPROVE')}
                        >
                          Approve
                        </button>
                        <button
                          type="button"
                          className="btn-orange-outline"
                          style={{ padding: '0.35rem 0.7rem', fontSize: '0.78rem' }}
                          onClick={() => handleCaseDecision(c.id, 'REJECT')}
                        >
                          Reject
                        </button>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}

            <h3 style={{ marginBottom: '0.65rem' }}>Active ASIGS Guardrail Rules ({data.rules.length})</h3>
            {data.rules.length === 0 ? (
              <p style={{ opacity: 0.7, fontSize: '0.85rem' }}>No rules seeded yet.</p>
            ) : (
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.84rem' }}>
                  <thead>
                    <tr style={{ textAlign: 'left', borderBottom: '1px solid rgba(0,0,0,0.1)' }}>
                      <th style={{ padding: '0.5rem' }}>Rule Code</th>
                      <th style={{ padding: '0.5rem' }}>Layer</th>
                      <th style={{ padding: '0.5rem' }}>Description</th>
                      <th style={{ padding: '0.5rem' }}>Default Outcome</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.rules.map((r) => (
                      <tr key={r.id} style={{ borderBottom: '1px solid rgba(0,0,0,0.06)' }}>
                        <td style={{ padding: '0.5rem', fontFamily: 'monospace', fontSize: '0.76rem' }}>
                          {r.rule_code}
                        </td>
                        <td style={{ padding: '0.5rem' }}>{r.layer}</td>
                        <td style={{ padding: '0.5rem' }}>{r.name}</td>
                        <td style={{ padding: '0.5rem', fontWeight: 600 }}>{r.default_outcome}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        )}

        {tab === 'craftproof' && (
          <AdminCraftProofTab adminToken={adminToken} toast={toast} />
        )}
      </main>

      {cardPreviewModal && (
        <div
          role="dialog"
          aria-modal="true"
          style={{
            position: 'fixed',
            inset: 0,
            zIndex: 9999,
            background: 'rgba(18, 16, 14, 0.72)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '1.25rem'
          }}
          onClick={closeCardPreviewModal}
        >
          <div
            className="fk-panel-card"
            style={{
              maxWidth: '720px',
              width: '100%',
              maxHeight: '90vh',
              overflowY: 'auto',
              padding: '1.25rem',
              background: '#fff'
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '1rem', marginBottom: '0.85rem' }}>
              <div>
                <h3 style={{ margin: 0 }}>
                  Artisan Card Inspection — {cardPreviewModal.storeName}
                </h3>
                <div style={{ fontSize: '0.8rem', opacity: 0.75 }}>
                  Application <code>{cardPreviewModal.appNumber}</code> • {cardPreviewModal.artisanName} •{' '}
                  <code>{cardPreviewModal.filename}</code>
                </div>
              </div>
              <button type="button" className="btn-orange-outline" onClick={closeCardPreviewModal}>
                Close
              </button>
            </div>

            <div
              style={{
                background: '#f7f4ee',
                border: '1px solid rgba(0,0,0,0.1)',
                borderRadius: '10px',
                padding: '0.75rem',
                textAlign: 'center',
                marginBottom: '1rem'
              }}
            >
              {cardPreviewModal.mimeType === 'application/pdf' ? (
                <iframe
                  title="Artisan Card PDF"
                  src={cardPreviewModal.blobUrl}
                  style={{ width: '100%', height: '480px', border: 'none', borderRadius: '6px' }}
                />
              ) : (
                <img
                  src={cardPreviewModal.blobUrl}
                  alt={`Artisan Card for ${cardPreviewModal.storeName}`}
                  style={{ maxWidth: '100%', maxHeight: '520px', objectFit: 'contain', borderRadius: '6px' }}
                />
              )}
            </div>

            {cardPreviewModal.status !== 'APPROVED' && (
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.6rem' }}>
                <button
                  type="button"
                  className="btn-orange-outline"
                  disabled={busyAppId === cardPreviewModal.applicationId}
                  onClick={() =>
                    handleDecideArtisanApplication(
                      {
                        id: cardPreviewModal.applicationId,
                        store_name: cardPreviewModal.storeName,
                        application_number: cardPreviewModal.appNumber
                      },
                      'REJECT'
                    )
                  }
                >
                  Reject Application
                </button>
                <button
                  type="button"
                  className="btn-orange"
                  disabled={busyAppId === cardPreviewModal.applicationId}
                  onClick={() =>
                    handleDecideArtisanApplication(
                      {
                        id: cardPreviewModal.applicationId,
                        store_name: cardPreviewModal.storeName,
                        application_number: cardPreviewModal.appNumber
                      },
                      'APPROVE'
                    )
                  }
                >
                  Verify Card &amp; Push Artisan Live
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </>
  );
}
