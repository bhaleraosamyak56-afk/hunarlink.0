import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import '../styles/portal.css';
import { useStore } from '../state/StoreContext';
import { useClerkBridge } from '../data/clerkConfig.js';
import {
  canAttemptBackend,
  createMyAddress,
  deleteMyAddress,
  exportMyPersonalData,
  fetchMyConsents,
  updateMyConsents
} from '../services/apiClient.js';
import PortalScope from '../components/PortalScope.jsx';
import { asset, formatINR } from '../utils/legacy.js';
import {
  IconAlert,
  IconArrowRight,
  IconBadgeCheck,
  IconCamera,
  IconCheck,
  IconHeart,
  IconHome,
  IconLogin,
  IconLogout,
  IconMapPin,
  IconPackage,
  IconPlus,
  IconReceipt,
  IconShield,
  IconSpark,
  IconUpload,
  IconUser
} from '../components/LineIcons.jsx';

const AVATAR_SWATCHES = [
  { hex: '#B4471F', name: 'Kashmiri Terracotta' },
  { hex: '#9A3412', name: 'Saffron Ember' },
  { hex: '#0D2B1D', name: 'Chinar Forest' },
  { hex: '#B88528', name: 'Zari Gold' },
  { hex: '#6B2D5C', name: 'Pashmina Plum' },
  { hex: '#1E4E79', name: 'Dal Indigo' }
];

const EMPTY_PROFILE = {
  firstName: '',
  lastName: '',
  fullName: '',
  email: '',
  phone: '',
  gender: '',
  dob: '',
  bio: '',
  preferredUpi: '',
  preferredPayment: 'Razorpay UPI Checkout',
  avatarColor: '#B4471F',
  avatarPhoto: '',
  badge: 'U',
  role: 'buyer',
  isLoggedIn: true,
  memberSince: ''
};

function computeBadge(firstName, lastName, email) {
  const f = (firstName || '').trim();
  const l = (lastName || '').trim();
  const e = (email || '').trim();
  const c1 = (f[0] || e[0] || 'U').toUpperCase();
  const c2 = (l[0] || f[1] || '').toUpperCase();
  return `${c1}${c2}`;
}

function readProfile(buyerProfile, storeUser) {
  const fullName =
    buyerProfile?.fullName ||
    storeUser?.fullName ||
    storeUser?.name ||
    '';
  const parts = fullName.trim().split(/\s+/).filter(Boolean);
  const firstName = buyerProfile?.firstName || parts[0] || '';
  const lastName = buyerProfile?.lastName || parts.slice(1).join(' ') || '';
  const email = buyerProfile?.email || storeUser?.email || '';
  const badge =
    buyerProfile?.badge ||
    storeUser?.badge ||
    computeBadge(firstName, lastName, email);

  return {
    ...EMPTY_PROFILE,
    ...(buyerProfile || {}),
    firstName,
    lastName,
    fullName: fullName || email || 'HunarLink Collector',
    email,
    phone: buyerProfile?.phone || storeUser?.phone || '',
    avatarColor: buyerProfile?.avatarColor || '#B4471F',
    badge,
    isLoggedIn: Boolean(storeUser && storeUser.isLoggedIn !== false)
  };
}

function profilesMatch(a, b) {
  if (a === b) return true;
  if (!a || !b) return false;
  const keys = Object.keys(EMPTY_PROFILE);
  for (const k of keys) {
    if ((a[k] ?? '') !== (b[k] ?? '')) return false;
  }
  return true;
}

function readAddresses(addresses) {
  return Array.isArray(addresses) ? addresses : [];
}

function resolveThumb(src) {
  if (!src) return asset('assets/image_1.jpg');
  if (/^https?:|^data:/.test(src)) return src;
  return asset(String(src).replace(/^\/+/, ''));
}

export default function ProfilePage() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const clerk = useClerkBridge();
  const {
    wishlist,
    wishlistItems,
    removeFromWishlist,
    addToCart,
    orders,
    setUser,
    user,
    buyerProfile,
    addresses: storeAddresses,
    setBuyerProfile,
    setAddresses: saveAddresses,
    hydrateFromBackend,
    toast
  } = useStore();

  const [profile, setProfile] = useState(() => readProfile(buyerProfile, user));
  const [savedSnapshot, setSavedSnapshot] = useState(null);
  const [addresses, setAddresses] = useState(() => readAddresses(storeAddresses));
  const [editing, setEditing] = useState({ personal: false, email: false, phone: false });

  const [tab, setTab] = useState(() => {
    const requested = params.get('tab');
    return ['personal', 'addresses', 'payments', 'wishlist'].includes(requested)
      ? requested
      : 'personal';
  });

  const [addrOpen, setAddrOpen] = useState(false);
  const [addrDraft, setAddrDraft] = useState({
    name: '',
    phone: '',
    pincode: '',
    city: '',
    locality: '',
    type: 'Home'
  });

  const [payDraft, setPayDraft] = useState({
    preferredUpi: profile.preferredUpi || '',
    preferredPayment: profile.preferredPayment || 'Razorpay UPI Checkout'
  });
  const [payDirty, setPayDirty] = useState(false);

  const [deletePanelOpen, setDeletePanelOpen] = useState(false);
  const [deletePassword, setDeletePassword] = useState('');
  const [deleteEmailCode, setDeleteEmailCode] = useState('');
  const [deleteCodeSent, setDeleteCodeSent] = useState(false);
  const [deleteReason, setDeleteReason] = useState('');
  const [deleteError, setDeleteError] = useState('');
  const [deletingAccount, setDeletingAccount] = useState(false);
  const [sendingDeleteCode, setSendingDeleteCode] = useState(false);

  const [consentsState, setConsentsState] = useState({
    marketing_updates: false,
    analytics_telemetry: false
  });
  const [exportingData, setExportingData] = useState(false);

  const photoInput = useRef(null);
  const avatarInput = useRef(null);
  const dpdpSectionRef = useRef(null);
  const deleteSectionRef = useRef(null);
  const profileRef = useRef(profile);
  profileRef.current = profile;

  const clerkUser = clerk?.clerkUser || null;
  const passwordEnabled = clerkUser ? Boolean(clerkUser.passwordEnabled) : true;
  const isEditingAny = editing.personal || editing.email || editing.phone;

  /* Unidirectional store -> local hydration (guarded against no-op loops). */
  useEffect(() => {
    const nextList = readAddresses(storeAddresses);
    setAddresses((prev) =>
      JSON.stringify(prev) === JSON.stringify(nextList) ? prev : nextList
    );
  }, [storeAddresses]);

  useEffect(() => {
    if (isEditingAny) return;
    if (!user?.email && !buyerProfile?.email) return;
    const hydrated = readProfile(buyerProfile, user);
    if (!profilesMatch(profileRef.current, hydrated)) {
      setProfile(hydrated);
      if (!payDirty) {
        setPayDraft({
          preferredUpi: hydrated.preferredUpi || '',
          preferredPayment: hydrated.preferredPayment || 'Razorpay UPI Checkout'
        });
      }
    }
  }, [user, buyerProfile, isEditingAny, payDirty]);

  useEffect(() => {
    let active = true;
    async function loadConsents() {
      if (!canAttemptBackend() || !clerk?.isSignedIn || !clerk?.getToken) return;
      try {
        const token = await clerk.getToken();
        if (!token || !active) return;
        const rows = await fetchMyConsents(token);
        if (!active || !Array.isArray(rows)) return;
        const next = { marketing_updates: false, analytics_telemetry: false };
        for (const r of rows) {
          if (r.consent_scope === 'marketing_updates') next.marketing_updates = Boolean(r.granted);
          if (r.consent_scope === 'analytics_telemetry') next.analytics_telemetry = Boolean(r.granted);
        }
        setConsentsState(next);
      } catch {
        /* non-fatal */
      }
    }
    loadConsents();
    return () => {
      active = false;
    };
  }, [clerk?.isSignedIn, clerk?.getToken]);

  const buildNormalizedProfile = useCallback((base, patch = {}) => {
    const merged = { ...base, ...patch };
    const first = String(merged.firstName ?? '').trim();
    const last = String(merged.lastName ?? '').trim();
    const email = String(merged.email ?? '').trim();
    const full = [first, last].filter(Boolean).join(' ') || merged.fullName || email;
    return {
      ...merged,
      firstName: first,
      lastName: last,
      email,
      fullName: full,
      badge: computeBadge(first, last, email)
    };
  }, []);

  /* Explicit persistence helper called ONLY on user commits (save, swatch, upload). */
  const commitProfile = useCallback(
    (patchOrNext) => {
      const next = buildNormalizedProfile(profileRef.current, patchOrNext);
      setProfile(next);
      setBuyerProfile(next);
      if (user && user.role !== 'artisan' && user.role !== 'seller' && next.email) {
        const nextName = next.firstName || user.name;
        const nextFull = next.fullName || user.fullName;
        const nextBadge = next.badge || user.badge;
        const nextPhone = next.phone || user.phone;
        if (
          user.name !== nextName ||
          user.fullName !== nextFull ||
          user.email !== next.email ||
          user.badge !== nextBadge ||
          user.phone !== nextPhone
        ) {
          setUser(
            {
              ...user,
              name: nextName,
              fullName: nextFull,
              email: next.email,
              phone: nextPhone,
              badge: nextBadge,
              authProvider: 'clerk',
              isLoggedIn: true
            },
            { silent: true }
          );
        }
      }
      return next;
    },
    [buildNormalizedProfile, setBuyerProfile, setUser, user]
  );

  function updateDraftField(patch) {
    setProfile((prev) => ({ ...prev, ...patch }));
  }

  function toggleSectionEdit(section) {
    const next = !editing[section];
    if (next) {
      setSavedSnapshot({ ...profileRef.current });
    } else if (savedSnapshot) {
      setProfile(savedSnapshot);
      setSavedSnapshot(null);
    }
    setEditing((e) => ({ ...e, [section]: next }));
  }

  function submitPersonal(e) {
    e.preventDefault();
    if (profile.dob) {
      const dobDate = new Date(`${profile.dob}T00:00:00Z`);
      if (!Number.isNaN(dobDate.getTime())) {
        const now = new Date();
        let age = now.getUTCFullYear() - dobDate.getUTCFullYear();
        const mDiff = now.getUTCMonth() - dobDate.getUTCMonth();
        if (mDiff < 0 || (mDiff === 0 && now.getUTCDate() < dobDate.getUTCDate())) {
          age -= 1;
        }
        if (age < 18) {
          toast(
            'Under DPDP Act Sec. 9, HunarLink accounts require users to be 18 years or older.',
            'error'
          );
          return;
        }
      }
    }
    commitProfile(profile);
    setSavedSnapshot(null);
    setEditing((ed) => ({ ...ed, personal: false }));
    toast('Personal information updated & synced across HunarLink!', 'success');
  }

  function submitEmail(e) {
    e.preventDefault();
    commitProfile({ email: profile.email });
    setSavedSnapshot(null);
    setEditing((ed) => ({ ...ed, email: false }));
    toast('Email address saved!', 'success');
  }

  function submitPhone(e) {
    e.preventDefault();
    commitProfile({ phone: profile.phone });
    setSavedSnapshot(null);
    setEditing((ed) => ({ ...ed, phone: false }));
    toast('Mobile number saved!', 'success');
  }

  function selectAvatarColor(hex) {
    commitProfile({ avatarColor: hex, avatarPhoto: '' });
    toast('Avatar theme updated!', 'success');
  }

  function uploadAvatar(ev) {
    const file = ev.target.files && ev.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      const img = new Image();
      img.onload = () => {
        const canvas = document.createElement('canvas');
        canvas.width = 180;
        canvas.height = 180;
        const minDim = Math.min(img.width, img.height);
        const sx = (img.width - minDim) / 2;
        const sy = (img.height - minDim) / 2;
        canvas.getContext('2d').drawImage(img, sx, sy, minDim, minDim, 0, 0, 180, 180);
        commitProfile({ avatarPhoto: canvas.toDataURL('image/jpeg', 0.85) });
        toast('Profile photo updated!', 'success');
      };
      img.src = reader.result;
    };
    reader.readAsDataURL(file);
    ev.target.value = '';
  }

  function removeAvatar() {
    commitProfile({ avatarPhoto: '' });
    toast('Profile photo removed.');
  }

  function submitPayments(e) {
    e.preventDefault();
    commitProfile({
      preferredUpi: payDraft.preferredUpi.trim(),
      preferredPayment: payDraft.preferredPayment
    });
    setPayDirty(false);
    toast('Payment & UPI preferences saved!', 'success');
  }

  async function submitAddress(e) {
    e.preventDefault();
    const payload = {
      address_label: (addrDraft.type || 'HOME').toUpperCase(),
      recipient_name: addrDraft.name.trim(),
      recipient_phone: addrDraft.phone.trim(),
      line1: addrDraft.locality.trim(),
      city: addrDraft.city.trim(),
      state_province: 'Jammu and Kashmir',
      postal_code: addrDraft.pincode.trim(),
      is_default: addresses.length === 0
    };
    try {
      const token = await clerk.getToken();
      if (canAttemptBackend() && token) {
        const saved = await createMyAddress(payload, token);
        await hydrateFromBackend(token);
        setAddrDraft({ name: '', phone: '', pincode: '', city: '', locality: '', type: 'Home' });
        setAddrOpen(false);
        toast(`Saved address "${saved.address_label}" to database!`, 'success');
        return;
      }
      toast('Backend database is unreachable. Could not save address.', 'error');
    } catch (err) {
      toast(err?.message || 'Could not save address to database.', 'error');
    }
  }

  function setDefaultAddress(id) {
    const idx = addresses.findIndex((a) => a.id === id);
    if (idx <= 0) return;
    const copy = [...addresses];
    const [item] = copy.splice(idx, 1);
    const reordered = [item, ...copy];
    setAddresses(reordered);
    saveAddresses(reordered);
    toast('Default delivery address updated!', 'success');
  }

  async function deleteAddress(id) {
    try {
      const token = await clerk.getToken();
      if (canAttemptBackend() && token) {
        await deleteMyAddress(id, token);
        await hydrateFromBackend(token);
        toast('Address removed from database.');
        return;
      }
    } catch (err) {
      toast(err?.message || 'Could not delete address.', 'error');
    }
  }

  async function signOut() {
    if (clerk.signOutClerk) await clerk.signOutClerk();
    toast('Signed out cleanly.');
    navigate('/login', { replace: true });
  }

  const jumpToPrivacy = () => {
    setTab('personal');
    setTimeout(() => {
      dpdpSectionRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }, 60);
  };

  const jumpToDelete = () => {
    setTab('personal');
    setDeletePanelOpen(true);
    setTimeout(() => {
      deleteSectionRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }, 60);
  };

  const personalLocked = !editing.personal;
  const displayInitials =
    profile.badge || computeBadge(profile.firstName, profile.lastName, profile.email);
  const greetingName = useMemo(() => {
    if (profile.firstName && profile.lastName) {
      return `${profile.firstName} ${profile.lastName}`.trim();
    }
    return profile.fullName || profile.firstName || profile.email || 'Collector';
  }, [profile.firstName, profile.lastName, profile.fullName, profile.email]);

  const activeOrderCount = Array.isArray(orders) ? orders.length : 0;

  return (
    <>
      <PortalScope family="user" />

      <header className="up-header">
        <div className="up-header-inner">
          <Link to="/" className="up-brand">
            <img
              src={`${import.meta.env.BASE_URL}img/brand/logo.svg`}
              alt=""
              className="up-emblem-mark"
              width="33"
              height="38"
            />
            <div>
              <div className="up-brand-title">HunarLink</div>
              <div className="up-brand-sub">Collector Account &amp; Profile</div>
            </div>
          </Link>
          <nav className="up-nav-links" aria-label="Account navigation">
            <Link to="/" className="up-nav-pill">
              <IconHome size={15} /> Storefront
            </Link>
            <Link to="/profile" className="up-nav-pill active">
              <IconUser size={15} /> My Profile
            </Link>
            <Link to="/orders" className="up-nav-pill">
              <IconPackage size={15} /> My Orders
            </Link>
            {profile.isLoggedIn ? (
              <button
                type="button"
                className="up-nav-pill up-nav-signout"
                id="nav-auth-pill"
                onClick={signOut}
              >
                <IconLogout size={15} /> Sign Out
              </button>
            ) : (
              <Link to="/login" className="up-nav-pill" id="nav-auth-pill">
                <IconLogin size={15} /> Switch / Login
              </Link>
            )}
          </nav>
        </div>
      </header>

      <main className="up-container up-profile-main" id="main-content">
        {/* COLLECTOR HERO BANNER */}
        <section className="up-prof-hero" aria-label="Account overview">
          <div className="up-prof-hero-main">
            <div className="fk-avatar-wrap up-hero-avatar-wrap">
              <div
                className="fk-avatar up-hero-avatar"
                id="sidebar-avatar"
                style={
                  profile.avatarPhoto
                    ? undefined
                    : { backgroundColor: profile.avatarColor || '#B4471F' }
                }
              >
                {profile.avatarPhoto ? (
                  <img
                    src={profile.avatarPhoto}
                    alt={greetingName}
                    width="74"
                    height="74"
                  />
                ) : (
                  displayInitials
                )}
              </div>
              <label className="fk-avatar-cam" title="Upload profile photo">
                <IconCamera size={12} />
                <input
                  type="file"
                  accept="image/*"
                  aria-label="Upload profile photo"
                  style={{ display: 'none' }}
                  ref={photoInput}
                  onChange={uploadAvatar}
                />
              </label>
            </div>

            <div className="up-prof-hero-copy">
              <div className="up-prof-hero-kicker">
                <IconBadgeCheck size={14} />
                <span>GI Patron Account &bull; DPDP Protected</span>
              </div>
              <h1 className="up-prof-hero-title" id="sidebar-fullname">
                Namaskar, {greetingName}
              </h1>
              <p className="up-prof-hero-sub">
                {profile.email || 'Signed in with Clerk'}
                {profile.phone ? ` \u2022 ${profile.phone}` : ''}
                {profile.preferredPayment ? ` \u2022 ${profile.preferredPayment}` : ''}
              </p>
            </div>
          </div>

          <div className="up-prof-stats">
            <button
              type="button"
              className="up-prof-stat-card"
              onClick={() => setTab('addresses')}
            >
              <span className="up-prof-stat-val">{addresses.length}</span>
              <span className="up-prof-stat-lbl">Saved Addresses</span>
            </button>
            <button
              type="button"
              className="up-prof-stat-card"
              onClick={() => setTab('wishlist')}
            >
              <span className="up-prof-stat-val">{wishlist.length}</span>
              <span className="up-prof-stat-lbl">Wishlist Crafts</span>
            </button>
            <Link to="/orders" className="up-prof-stat-card">
              <span className="up-prof-stat-val">{activeOrderCount}</span>
              <span className="up-prof-stat-lbl">Orders Tracked</span>
            </Link>
            <button
              type="button"
              className="up-prof-stat-card up-prof-stat-emerald"
              onClick={jumpToPrivacy}
            >
              <span className="up-prof-stat-val">
                <IconShield size={18} />
              </span>
              <span className="up-prof-stat-lbl">DPDP Controls</span>
            </button>
          </div>
        </section>

        {/* TWO-COLUMN COLLECTOR WORKSPACE */}
        <div className="fk-account-grid up-prof-grid">
          {/* LEFT SIDEBAR RAIL */}
          <aside className="fk-sidebar up-prof-sidebar" aria-label="Profile sections">
            <div className="fk-nav-card up-prof-nav-card">
              <div className="fk-nav-section" style={{ padding: '6px 0' }}>
                <Link to="/orders" className="fk-nav-group-link up-prof-orders-link">
                  <span className="up-nav-row-label">
                    <IconPackage size={16} />
                    <span>My Orders &amp; Loom Tracking</span>
                  </span>
                  <IconArrowRight size={14} />
                </Link>
              </div>

              <div className="fk-nav-section">
                <div className="fk-nav-group-title">
                  <span>ACCOUNT SETTINGS</span>
                </div>
                <button
                  type="button"
                  className={`fk-nav-item${tab === 'personal' ? ' active' : ''}`}
                  data-view="personal"
                  onClick={() => setTab('personal')}
                >
                  <span className="up-nav-row-label">
                    <IconUser size={15} />
                    <span>Profile Information</span>
                  </span>
                </button>
                <button
                  type="button"
                  className={`fk-nav-item${tab === 'addresses' ? ' active' : ''}`}
                  data-view="addresses"
                  onClick={() => setTab('addresses')}
                >
                  <span className="up-nav-row-label">
                    <IconMapPin size={15} />
                    <span>Manage Addresses</span>
                  </span>
                  <span className="up-nav-badge" id="nav-addr-count">
                    {addresses.length}
                  </span>
                </button>
                <button
                  type="button"
                  className={`fk-nav-item${tab === 'payments' ? ' active' : ''}`}
                  data-view="payments"
                  onClick={() => setTab('payments')}
                >
                  <span className="up-nav-row-label">
                    <IconReceipt size={15} />
                    <span>Saved UPI &amp; Payments</span>
                  </span>
                </button>
              </div>

              <div className="fk-nav-section">
                <div className="fk-nav-group-title">
                  <span>COLLECTION &amp; PRIVACY</span>
                </div>
                <button
                  type="button"
                  className={`fk-nav-item${tab === 'wishlist' ? ' active' : ''}`}
                  data-view="wishlist"
                  onClick={() => setTab('wishlist')}
                >
                  <span className="up-nav-row-label">
                    <IconHeart size={15} />
                    <span>My Wishlist</span>
                  </span>
                  <span className="up-nav-badge" id="nav-wish-count">
                    {wishlist.length}
                  </span>
                </button>
                <button type="button" className="fk-nav-item" onClick={jumpToPrivacy}>
                  <span className="up-nav-row-label">
                    <IconShield size={15} />
                    <span>DPDP Data &amp; Consents</span>
                  </span>
                </button>
                <Link to="/orders" className="fk-nav-item" style={{ textDecoration: 'none' }}>
                  <span className="up-nav-row-label">
                    <IconSpark size={15} />
                    <span>My Reviews &amp; Ratings</span>
                  </span>
                  <IconArrowRight size={13} />
                </Link>
              </div>

              <div className="fk-nav-section up-prof-danger-rail">
                <button type="button" className="fk-nav-item up-rail-danger" onClick={signOut}>
                  <span className="up-nav-row-label">
                    <IconLogout size={15} />
                    <span>Sign Out</span>
                  </span>
                </button>
                <button type="button" className="fk-nav-item up-rail-danger" onClick={jumpToDelete}>
                  <span className="up-nav-row-label">
                    <IconAlert size={15} />
                    <span>Delete Account</span>
                  </span>
                </button>
              </div>
            </div>
          </aside>

          {/* RIGHT MAIN WORKSPACE */}
          <section className="fk-panel-card up-prof-panel">
            {/* TAB 1: PERSONAL INFORMATION, CONTACT, DPDP PRIVACY, FAQS, DELETE */}
            <div className={`fk-tab-view${tab === 'personal' ? ' active' : ''}`} id="view-personal">
              {/* Block A: Personal Information & Avatar Studio */}
              <div className="fk-section-block up-prof-card-block">
                <div className="fk-block-head up-block-head-split">
                  <div className="up-block-title-wrap">
                    <span className="up-block-icon">
                      <IconUser size={18} />
                    </span>
                    <div>
                      <h2 className="fk-block-title">Personal Information</h2>
                      <p className="up-block-sub">
                        Appears on GI authenticity certificates &amp; collector orders.
                      </p>
                    </div>
                  </div>
                  <div className="up-block-actions">
                    <span className={`up-status-chip${editing.personal ? ' is-editing' : ''}`}>
                      {editing.personal ? 'Editing' : 'Saved'}
                    </span>
                    <button
                      type="button"
                      className="btn-orange-outline up-edit-pill"
                      id="btn-edit-personal"
                      onClick={() => toggleSectionEdit('personal')}
                    >
                      {editing.personal ? 'Cancel' : 'Edit Profile'}
                    </button>
                  </div>
                </div>

                <form id="form-personal" onSubmit={submitPersonal}>
                  <div className="form-row-2" style={{ marginBottom: '16px' }}>
                    <div>
                      <label className="up-label" htmlFor="prof-first">
                        First Name
                      </label>
                      <input
                        type="text"
                        id="prof-first"
                        className="up-input"
                        required
                        disabled={personalLocked}
                        value={profile.firstName || ''}
                        onChange={(e) => updateDraftField({ firstName: e.target.value })}
                      />
                    </div>
                    <div>
                      <label className="up-label" htmlFor="prof-last">
                        Last Name
                      </label>
                      <input
                        type="text"
                        id="prof-last"
                        className="up-input"
                        disabled={personalLocked}
                        value={profile.lastName || ''}
                        onChange={(e) => updateDraftField({ lastName: e.target.value })}
                      />
                    </div>
                  </div>

                  <div className="form-row-2" style={{ marginBottom: '16px' }}>
                    <div>
                      <span className="up-label" id="prof-gender-label">
                        Your Gender
                      </span>
                      <div
                        className="gender-radio-row up-choice-group"
                        role="radiogroup"
                        aria-labelledby="prof-gender-label"
                      >
                        {['Female', 'Male', 'Prefer not to say'].map((g) => (
                          <label
                            className={`up-choice-pill${profile.gender === g ? ' active' : ''}${personalLocked ? ' disabled' : ''}`}
                            key={g}
                          >
                            <input
                              type="radio"
                              name="prof-gender"
                              value={g}
                              disabled={personalLocked}
                              checked={profile.gender === g}
                              onChange={() => updateDraftField({ gender: g })}
                            />
                            <span>{g}</span>
                          </label>
                        ))}
                      </div>
                    </div>
                    <div>
                      <label className="up-label" htmlFor="prof-dob">
                        Date of Birth
                      </label>
                      <input
                        type="date"
                        id="prof-dob"
                        className="up-input"
                        disabled={personalLocked}
                        value={profile.dob || ''}
                        onChange={(e) => updateDraftField({ dob: e.target.value })}
                      />
                    </div>
                  </div>

                  <div style={{ marginBottom: '18px' }}>
                    <label className="up-label" htmlFor="prof-bio">
                      Collector Bio &amp; Craft Preferences
                    </label>
                    <textarea
                      id="prof-bio"
                      className="up-textarea"
                      rows="2"
                      placeholder="Tell Kashmir's master artisans about your favorite weaves, motifs, or heirloom interests..."
                      disabled={personalLocked}
                      value={profile.bio || ''}
                      onChange={(e) => updateDraftField({ bio: e.target.value })}
                    />
                  </div>

                  {/* Avatar Studio */}
                  <div className="up-avatar-studio">
                    <span className="up-label" id="prof-avatar-label">
                      Avatar Theme &amp; Portrait
                    </span>
                    <div className="up-avatar-studio-row">
                      <div
                        className="up-avatar-preview"
                        style={
                          profile.avatarPhoto
                            ? undefined
                            : { backgroundColor: profile.avatarColor || '#B4471F' }
                        }
                      >
                        {profile.avatarPhoto ? (
                          <img
                            src={profile.avatarPhoto}
                            alt=""
                            width="48"
                            height="48"
                          />
                        ) : (
                          displayInitials
                        )}
                      </div>

                      <div
                        className="avatar-color-swatches"
                        id="avatar-swatches"
                        role="group"
                        aria-labelledby="prof-avatar-label"
                      >
                        {AVATAR_SWATCHES.map(({ hex, name }) => {
                          const selected =
                            !profile.avatarPhoto &&
                            (profile.avatarColor || '#B4471F') === hex;
                          return (
                            <button
                              type="button"
                              key={hex}
                              className={`swatch-btn${selected ? ' selected' : ''}`}
                              style={{ background: hex }}
                              title={name}
                              aria-label={`Use ${name} avatar color`}
                              aria-pressed={selected}
                              onClick={() => selectAvatarColor(hex)}
                            >
                              {selected && <IconCheck size={12} />}
                            </button>
                          );
                        })}
                      </div>

                      <div className="up-avatar-upload-actions">
                        <label className="btn-orange-outline up-upload-pill">
                          <IconUpload size={14} />
                          <span>Upload Photo</span>
                          <input
                            type="file"
                            accept="image/*"
                            aria-label="Upload profile photo from studio"
                            style={{ display: 'none' }}
                            ref={avatarInput}
                            onChange={uploadAvatar}
                          />
                        </label>
                        {profile.avatarPhoto && (
                          <button
                            type="button"
                            className="btn-link-edit"
                            onClick={removeAvatar}
                          >
                            Remove Photo
                          </button>
                        )}
                      </div>
                    </div>
                  </div>

                  {editing.personal && (
                    <div id="save-personal-row" className="up-save-bar">
                      <button type="submit" className="btn-orange">
                        <IconCheck size={14} /> Save Changes
                      </button>
                    </div>
                  )}
                </form>
              </div>

              {/* Block B & C: Email & Mobile Contact Cards */}
              <div className="up-contact-split">
                <div className="up-contact-card">
                  <div className="fk-block-head up-block-head-split" style={{ marginBottom: '10px' }}>
                    <div>
                      <h2 className="fk-block-title up-title-sm">Email Address</h2>
                      <p className="up-block-sub">Used for GI receipts &amp; security alerts</p>
                    </div>
                    <button
                      type="button"
                      className="btn-link-edit"
                      id="btn-edit-email"
                      onClick={() => toggleSectionEdit('email')}
                    >
                      {editing.email ? 'Cancel' : 'Edit'}
                    </button>
                  </div>
                  <form id="form-email" onSubmit={submitEmail} className="up-inline-form">
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <label className="up-label" htmlFor="prof-email">
                        Primary Email
                      </label>
                      <input
                        type="email"
                        id="prof-email"
                        className="up-input"
                        required
                        disabled={!editing.email}
                        value={profile.email || ''}
                        onChange={(e) => updateDraftField({ email: e.target.value })}
                      />
                    </div>
                    {editing.email && (
                      <button type="submit" className="btn-orange" id="save-email-btn">
                        Save
                      </button>
                    )}
                  </form>
                </div>

                <div className="up-contact-card">
                  <div className="fk-block-head up-block-head-split" style={{ marginBottom: '10px' }}>
                    <div>
                      <h2 className="fk-block-title up-title-sm">Mobile Number</h2>
                      <p className="up-block-sub">Insured loom dispatch &amp; OTP delivery</p>
                    </div>
                    <button
                      type="button"
                      className="btn-link-edit"
                      id="btn-edit-phone"
                      onClick={() => toggleSectionEdit('phone')}
                    >
                      {editing.phone ? 'Cancel' : 'Edit'}
                    </button>
                  </div>
                  <form id="form-phone" onSubmit={submitPhone} className="up-inline-form">
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <label className="up-label" htmlFor="prof-phone">
                        Phone Number
                      </label>
                      <input
                        type="tel"
                        id="prof-phone"
                        className="up-input"
                        placeholder="+91 98112 77420"
                        required
                        disabled={!editing.phone}
                        value={profile.phone || ''}
                        onChange={(e) => updateDraftField({ phone: e.target.value })}
                      />
                    </div>
                    {editing.phone && (
                      <button type="submit" className="btn-orange" id="save-phone-btn">
                        Save
                      </button>
                    )}
                  </form>
                </div>
              </div>

              {/* Block D2: DPDP Privacy Controls & Data Export */}
              <div className="up-dpdp-card" ref={dpdpSectionRef}>
                <div className="fk-block-head up-block-head-split" style={{ marginBottom: '10px' }}>
                  <div className="up-block-title-wrap">
                    <span className="up-block-icon up-block-icon-emerald">
                      <IconShield size={18} />
                    </span>
                    <div>
                      <h3 className="up-dpdp-title">
                        DPDP Privacy Controls &amp; Your Data Rights
                      </h3>
                      <p className="up-block-sub">
                        Manage optional consents under India&apos;s DPDP Act 2023 or download your records.
                      </p>
                    </div>
                  </div>
                  <button
                    type="button"
                    className="btn-orange-outline"
                    disabled={exportingData}
                    onClick={async () => {
                      setExportingData(true);
                      try {
                        let payload = {
                          profile,
                          addresses,
                          exported_at: new Date().toISOString(),
                          source: 'local-fallback'
                        };
                        if (canAttemptBackend() && clerk.getToken) {
                          const token = await clerk.getToken();
                          if (token) {
                            payload = await exportMyPersonalData(token);
                          }
                        }
                        const blob = new Blob([JSON.stringify(payload, null, 2)], {
                          type: 'application/json'
                        });
                        const url = URL.createObjectURL(blob);
                        const link = document.createElement('a');
                        link.href = url;
                        link.download = 'hunarlink-my-personal-data.json';
                        link.click();
                        URL.revokeObjectURL(url);
                        toast('Personal data JSON exported.', 'success');
                      } catch (err) {
                        toast(err?.message || 'Could not export personal data.', 'error');
                      } finally {
                        setExportingData(false);
                      }
                    }}
                  >
                    <IconUpload size={14} />
                    <span>{exportingData ? 'Exporting\u2026' : 'Download My Data (JSON)'}</span>
                  </button>
                </div>

                <div className="up-consent-list">
                  <label className="up-consent-row">
                    <input
                      type="checkbox"
                      checked={consentsState.marketing_updates}
                      onChange={async (e) => {
                        const next = e.target.checked;
                        setConsentsState((s) => ({ ...s, marketing_updates: next }));
                        try {
                          if (canAttemptBackend() && clerk.getToken) {
                            const token = await clerk.getToken();
                            if (token) {
                              await updateMyConsents(
                                { consents: [{ consent_scope: 'marketing_updates', granted: next }] },
                                token
                              );
                            }
                          }
                          toast(
                            next ? 'Craft dispatches opted in.' : 'Marketing consent withdrawn.',
                            'success'
                          );
                        } catch (err) {
                          toast(err?.message || 'Could not update consent.', 'error');
                        }
                      }}
                    />
                    <span>
                      <strong>Seasonal Valley Chronicle Emails (Optional)</strong>
                      <small>Receive occasional stories about master loom releases and exhibitions.</small>
                    </span>
                  </label>
                  <label className="up-consent-row">
                    <input
                      type="checkbox"
                      checked={consentsState.analytics_telemetry}
                      onChange={async (e) => {
                        const next = e.target.checked;
                        setConsentsState((s) => ({ ...s, analytics_telemetry: next }));
                        try {
                          if (canAttemptBackend() && clerk.getToken) {
                            const token = await clerk.getToken();
                            if (token) {
                              await updateMyConsents(
                                {
                                  consents: [{ consent_scope: 'analytics_telemetry', granted: next }]
                                },
                                token
                              );
                            }
                          }
                          toast(
                            next ? 'Craft analytics enabled.' : 'Analytics consent withdrawn.',
                            'success'
                          );
                        } catch (err) {
                          toast(err?.message || 'Could not update consent.', 'error');
                        }
                      }}
                    />
                    <span>
                      <strong>Privacy-Safe Storefront Analytics (Optional)</strong>
                      <small>Helps us improve craft discovery without third-party ad trackers.</small>
                    </span>
                  </label>
                </div>

                <Link to="/privacy" className="btn-link-edit up-privacy-link">
                  Read HunarLink DPDP Privacy Promise &rarr;
                </Link>
              </div>

              {/* Block D: Collector FAQs */}
              <div className="fk-section-block up-faq-block">
                <h3 className="up-faq-heading">Account &amp; GI Record FAQs</h3>
                <div className="up-faq-grid">
                  <details className="up-faq-card" open>
                    <summary className="faq-q">
                      What happens when I update my name, email, or mobile number?
                    </summary>
                    <p className="faq-a">
                      Your updated profile immediately syncs across the HunarLink storefront header,
                      future GI Ownership Certificates, and live loom-to-door tracking alerts.
                    </p>
                  </details>
                  <details className="up-faq-card">
                    <summary className="faq-q">
                      Are my saved delivery addresses available during checkout?
                    </summary>
                    <p className="faq-a">
                      Yes. Every address you add or mark as default under Manage Addresses appears
                      automatically inside HunarLink Checkout.
                    </p>
                  </details>
                </div>
              </div>

              {/* Block E: Permanent Account Deletion */}
              <div className="up-danger-card" ref={deleteSectionRef}>
                <div className="fk-block-head up-block-head-split" style={{ marginBottom: '8px' }}>
                  <div className="up-block-title-wrap">
                    <span className="up-block-icon up-block-icon-danger">
                      <IconAlert size={18} />
                    </span>
                    <div>
                      <h3 className="up-danger-title">Delete Account</h3>
                      <p className="up-block-sub">
                        Permanent account closure &amp; DPDP erasure workflow
                      </p>
                    </div>
                  </div>
                  <button
                    type="button"
                    className="btn-link-edit up-danger-toggle"
                    onClick={() => {
                      setDeletePanelOpen((v) => !v);
                      setDeleteError('');
                    }}
                  >
                    {deletePanelOpen ? 'Cancel' : 'Deactivate & Delete'}
                  </button>
                </div>
                <p className="up-danger-copy">
                  Permanently delete your HunarLink account, saved addresses, and wishlist. Active
                  orders in progress must be delivered or cancelled first. Once deleted, you cannot
                  log back into this account and must register again to return.
                </p>

                {deletePanelOpen && (
                  <form
                    className="up-delete-form"
                    onSubmit={async (e) => {
                      e.preventDefault();
                      setDeleteError('');
                      if (!clerk?.enabled || typeof clerk.deleteMyAccount !== 'function') {
                        setDeleteError(
                          'Account deletion requires an active Clerk authentication session.'
                        );
                        return;
                      }
                      setDeletingAccount(true);
                      try {
                        await clerk.deleteMyAccount({
                          currentPassword: deletePassword,
                          emailCode: deleteEmailCode,
                          reason: deleteReason
                        });
                        toast('Your HunarLink account has been permanently deleted.');
                        navigate('/register?account_deleted=1', { replace: true });
                      } catch (err) {
                        setDeleteError(
                          err?.message || 'Could not delete your account. Please try again.'
                        );
                      } finally {
                        setDeletingAccount(false);
                      }
                    }}
                  >
                    {deleteError && (
                      <div role="alert" className="up-delete-alert">
                        {deleteError}
                      </div>
                    )}

                    {passwordEnabled ? (
                      <div style={{ marginBottom: '12px' }}>
                        <label className="up-label" htmlFor="delete-current-password">
                          Enter Your Current Password to Confirm *
                        </label>
                        <input
                          type="password"
                          id="delete-current-password"
                          className="up-input"
                          required
                          autoComplete="current-password"
                          placeholder="Current account password"
                          value={deletePassword}
                          onChange={(e) => setDeletePassword(e.target.value)}
                        />
                      </div>
                    ) : (
                      <div style={{ marginBottom: '12px' }}>
                        <p className="up-danger-oauth-note">
                          Your account signs in with Google / Apple (no password set). Request a
                          6-digit verification code sent to <strong>{profile.email}</strong> to
                          confirm deletion.
                        </p>
                        <div className="up-delete-code-actions">
                          <button
                            type="button"
                            className="btn-orange-outline"
                            disabled={sendingDeleteCode || deletingAccount}
                            onClick={async () => {
                              setDeleteError('');
                              setSendingDeleteCode(true);
                              try {
                                await clerk.sendDeleteVerificationCode();
                                setDeleteCodeSent(true);
                                toast('Verification code sent to your email.');
                              } catch (err) {
                                setDeleteError(err?.message || 'Could not send verification code.');
                              } finally {
                                setSendingDeleteCode(false);
                              }
                            }}
                          >
                            {sendingDeleteCode
                              ? 'Sending...'
                              : deleteCodeSent
                                ? 'Resend Code'
                                : 'Send Verification Code'}
                          </button>
                        </div>
                        {deleteCodeSent && (
                          <div>
                            <label className="up-label" htmlFor="delete-email-code">
                              6-Digit Email Verification Code *
                            </label>
                            <input
                              type="text"
                              id="delete-email-code"
                              className="up-input"
                              required
                              inputMode="numeric"
                              placeholder="Enter 6-digit code"
                              value={deleteEmailCode}
                              onChange={(e) => setDeleteEmailCode(e.target.value)}
                            />
                          </div>
                        )}
                      </div>
                    )}

                    <div style={{ marginBottom: '14px' }}>
                      <label className="up-label" htmlFor="delete-reason">
                        Reason (Optional)
                      </label>
                      <input
                        type="text"
                        id="delete-reason"
                        className="up-input"
                        placeholder="Optional feedback"
                        value={deleteReason}
                        onChange={(e) => setDeleteReason(e.target.value)}
                      />
                    </div>

                    <button
                      type="submit"
                      className="btn-orange up-delete-submit"
                      disabled={deletingAccount || (!passwordEnabled && !deleteCodeSent)}
                    >
                      {deletingAccount
                        ? 'Deleting Account...'
                        : 'Permanently Delete My Account'}
                    </button>
                  </form>
                )}
              </div>
            </div>

            {/* TAB 2: MANAGE ADDRESSES */}
            <div className={`fk-tab-view${tab === 'addresses' ? ' active' : ''}`} id="view-addresses">
              <div className="fk-block-head up-block-head-split">
                <div className="up-block-title-wrap">
                  <span className="up-block-icon">
                    <IconMapPin size={18} />
                  </span>
                  <div>
                    <h2 className="fk-block-title">Manage Delivery Addresses</h2>
                    <p className="up-block-sub">
                      Synced directly with HunarLink Insured Checkout
                    </p>
                  </div>
                </div>
                <button
                  type="button"
                  className="btn-orange"
                  onClick={() => setAddrOpen((v) => !v)}
                >
                  <IconPlus size={15} />
                  <span>{addrOpen ? 'Close Form' : 'Add New Address'}</span>
                </button>
              </div>

              {addrOpen && (
                <form
                  id="new-address-form"
                  className="up-address-form-card"
                  onSubmit={submitAddress}
                >
                  <h3 className="up-address-form-title">Add a New Delivery Address</h3>
                  <div className="form-row-2" style={{ marginBottom: '12px' }}>
                    <div>
                      <label className="up-label" htmlFor="addr-name">
                        Receiver Full Name *
                      </label>
                      <input
                        type="text"
                        id="addr-name"
                        className="up-input"
                        required
                        placeholder="Full recipient name"
                        value={addrDraft.name}
                        onChange={(e) => setAddrDraft({ ...addrDraft, name: e.target.value })}
                      />
                    </div>
                    <div>
                      <label className="up-label" htmlFor="addr-phone">
                        10-Digit Mobile Number *
                      </label>
                      <input
                        type="tel"
                        id="addr-phone"
                        className="up-input"
                        required
                        placeholder="e.g. +91 98112 77420"
                        value={addrDraft.phone}
                        onChange={(e) => setAddrDraft({ ...addrDraft, phone: e.target.value })}
                      />
                    </div>
                  </div>
                  <div className="form-row-2" style={{ marginBottom: '12px' }}>
                    <div>
                      <label className="up-label" htmlFor="addr-pin">
                        Pincode *
                      </label>
                      <input
                        type="text"
                        id="addr-pin"
                        className="up-input"
                        required
                        placeholder="e.g. 110024"
                        value={addrDraft.pincode}
                        onChange={(e) => setAddrDraft({ ...addrDraft, pincode: e.target.value })}
                      />
                    </div>
                    <div>
                      <label className="up-label" htmlFor="addr-city">
                        City &amp; State *
                      </label>
                      <input
                        type="text"
                        id="addr-city"
                        className="up-input"
                        required
                        placeholder="e.g. New Delhi"
                        value={addrDraft.city}
                        onChange={(e) => setAddrDraft({ ...addrDraft, city: e.target.value })}
                      />
                    </div>
                  </div>
                  <div style={{ marginBottom: '14px' }}>
                    <label className="up-label" htmlFor="addr-loc">
                      House No., Street, Locality &amp; Landmark *
                    </label>
                    <input
                      type="text"
                      id="addr-loc"
                      className="up-input"
                      required
                      placeholder="e.g. B-42 Defence Colony, Ring Road"
                      value={addrDraft.locality}
                      onChange={(e) => setAddrDraft({ ...addrDraft, locality: e.target.value })}
                    />
                  </div>
                  <div style={{ marginBottom: '16px' }}>
                    <span className="up-label" id="addr-type-label">
                      Address Type
                    </span>
                    <div
                      className="gender-radio-row up-choice-group"
                      role="radiogroup"
                      aria-labelledby="addr-type-label"
                    >
                      {[
                        ['Home', 'Home'],
                        ['Work', 'Work / Office']
                      ].map(([value, label]) => (
                        <label
                          className={`up-choice-pill${addrDraft.type === value ? ' active' : ''}`}
                          key={value}
                        >
                          <input
                            type="radio"
                            name="addr-type"
                            value={value}
                            checked={addrDraft.type === value}
                            onChange={() => setAddrDraft({ ...addrDraft, type: value })}
                          />
                          <span>{label}</span>
                        </label>
                      ))}
                    </div>
                  </div>
                  <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
                    <button type="submit" className="btn-orange">
                      Save Address
                    </button>
                    <button
                      type="button"
                      className="btn-orange-outline"
                      onClick={() => setAddrOpen(false)}
                    >
                      Cancel
                    </button>
                  </div>
                </form>
              )}

              <div id="addresses-list" className="up-addresses-grid">
                {addresses.length === 0 ? (
                  <div className="up-empty-state">
                    <span className="up-empty-icon">
                      <IconMapPin size={22} />
                    </span>
                    <h3>No saved delivery addresses yet</h3>
                    <p>
                      Add a home or studio delivery address so future GI heirloom checkouts stay
                      one click away.
                    </p>
                    <button
                      type="button"
                      className="btn-orange"
                      onClick={() => setAddrOpen(true)}
                    >
                      <IconPlus size={14} /> Add Delivery Address
                    </button>
                  </div>
                ) : (
                  addresses.map((a, idx) => (
                    <article
                      className={`address-card up-address-item${idx === 0 ? ' default-addr' : ''}`}
                      key={a.id}
                    >
                      <div className="up-address-body">
                        <div className="up-address-chips">
                          <span className="addr-type-chip">{a.type || 'Home'}</span>
                          {idx === 0 && <span className="addr-type-chip is-default">DEFAULT</span>}
                        </div>
                        <div className="up-address-name">
                          {a.name} &bull; {a.phone}
                        </div>
                        <div className="up-address-lines">
                          {a.locality}, {a.city} &mdash; <strong>{a.pincode}</strong>
                        </div>
                      </div>
                      <div className="up-address-actions">
                        {idx !== 0 && (
                          <button
                            type="button"
                            className="btn-orange-outline"
                            style={{ padding: '6px 11px', fontSize: '0.74rem' }}
                            onClick={() => setDefaultAddress(a.id)}
                          >
                            Set Default
                          </button>
                        )}
                        <button
                          type="button"
                          className="btn-link-edit"
                          style={{ color: 'var(--danger-600)' }}
                          onClick={() => deleteAddress(a.id)}
                        >
                          Delete
                        </button>
                      </div>
                    </article>
                  ))
                )}
              </div>
            </div>

            {/* TAB 3: SAVED UPI & PAYMENT PREFERENCES */}
            <div className={`fk-tab-view${tab === 'payments' ? ' active' : ''}`} id="view-payments">
              <div className="fk-block-head up-block-head-split">
                <div className="up-block-title-wrap">
                  <span className="up-block-icon">
                    <IconReceipt size={18} />
                  </span>
                  <div>
                    <h2 className="fk-block-title">Saved UPI &amp; Payment Preferences</h2>
                    <p className="up-block-sub">
                      Pre-select your checkout rail for fast Razorpay settlement
                    </p>
                  </div>
                </div>
              </div>

              <div className="up-pci-banner">
                <IconShield size={18} />
                <div>
                  <strong>PCI-DSS SAQ-A Hosted Security</strong>
                  <p>
                    HunarLink never collects or stores debit/credit card numbers on our servers. All
                    card transactions run directly through Razorpay&apos;s encrypted hosted modal.
                  </p>
                </div>
              </div>

              <form className="up-payments-form" onSubmit={submitPayments}>
                <div className="form-field">
                  <label className="up-label" htmlFor="prof-upi">
                    Preferred UPI ID (Razorpay Instant Pay)
                  </label>
                  <input
                    type="text"
                    id="prof-upi"
                    className="up-input"
                    placeholder="e.g. collector@okaxis"
                    value={payDraft.preferredUpi}
                    onChange={(e) => {
                      setPayDirty(true);
                      setPayDraft({ ...payDraft, preferredUpi: e.target.value });
                    }}
                  />
                </div>
                <div className="form-field">
                  <label className="up-label" htmlFor="prof-pay-mode">
                    Default Checkout Method
                  </label>
                  <select
                    id="prof-pay-mode"
                    className="up-select"
                    value={payDraft.preferredPayment}
                    onChange={(e) => {
                      setPayDirty(true);
                      setPayDraft({ ...payDraft, preferredPayment: e.target.value });
                    }}
                  >
                    <option value="Razorpay UPI Checkout">Razorpay UPI Checkout (Zero Fee)</option>
                    <option value="Insured Cash on Delivery">Insured Cash on Delivery (COD)</option>
                    <option value="Razorpay Hosted Card Checkout">
                      Credit / Debit Card (Razorpay Hosted)
                    </option>
                  </select>
                </div>
                <button type="submit" className="btn-orange">
                  <IconCheck size={14} /> Save Payment Preference
                </button>
              </form>
            </div>

            {/* TAB 4: MY WISHLIST */}
            <div className={`fk-tab-view${tab === 'wishlist' ? ' active' : ''}`} id="view-wishlist">
              <div className="fk-block-head up-block-head-split">
                <div className="up-block-title-wrap">
                  <span className="up-block-icon">
                    <IconHeart size={18} />
                  </span>
                  <div>
                    <h2 className="fk-block-title">My Saved Heirloom Wishlist</h2>
                    <p className="up-block-sub">
                      {wishlist.length} {wishlist.length === 1 ? 'craft piece' : 'craft pieces'} saved
                      for future acquisition
                    </p>
                  </div>
                </div>
                <Link to="/#marketplace-section" className="btn-orange-outline">
                  Explore More Crafts &rarr;
                </Link>
              </div>

              <div id="wishlist-container" className="up-wishlist-grid">
                {wishlist.length === 0 ? (
                  <div className="up-empty-state">
                    <span className="up-empty-icon">
                      <IconHeart size={22} />
                    </span>
                    <h3>Your heirloom wishlist is empty</h3>
                    <p>
                      Browse GI-certified Kashmiri shawls, walnut woodcarving, and Sozni textiles to
                      bookmark pieces here.
                    </p>
                    <Link to="/#marketplace-section" className="btn-orange">
                      Explore J&amp;K Heritage Store &rarr;
                    </Link>
                  </div>
                ) : (
                  wishlistItems.map((p) => (
                    <article className="up-wish-card" key={p.id}>
                      <Link
                        to={`/product?id=${encodeURIComponent(p.id)}`}
                        className="up-wish-thumb-link"
                        aria-label={`View ${p.title}`}
                      >
                        <img
                          src={resolveThumb(p.image)}
                          alt={p.title}
                          width="96"
                          height="112"
                          className="up-wish-thumb"
                        />
                      </Link>
                      <div className="up-wish-body">
                        <span className="up-wish-guild">
                          {p.guildLabel || 'GI-Certified Kashmiri Craft'}
                        </span>
                        <Link
                          to={`/product?id=${encodeURIComponent(p.id)}`}
                          className="up-wish-title"
                        >
                          {p.title}
                        </Link>
                        {p.artisan && <span className="up-wish-artisan">{p.artisan}</span>}
                        {typeof p.price === 'number' && (
                          <span className="up-wish-price">{formatINR(p.price)}</span>
                        )}
                      </div>
                      <div className="up-wish-actions">
                        <button
                          type="button"
                          className="btn-orange"
                          style={{ padding: '8px 13px', fontSize: '0.76rem' }}
                          onClick={() => addToCart(p.id, 1)}
                        >
                          Add to Bag
                        </button>
                        <Link
                          to={`/product?id=${encodeURIComponent(p.id)}`}
                          className="btn-orange-outline"
                          style={{ padding: '7px 12px', fontSize: '0.75rem' }}
                        >
                          View Craft
                        </Link>
                        <button
                          type="button"
                          className="btn-link-edit"
                          style={{ color: 'var(--danger-600)' }}
                          onClick={() => removeFromWishlist(p.id)}
                        >
                          Remove
                        </button>
                      </div>
                    </article>
                  ))
                )}
              </div>
            </div>
          </section>
        </div>
      </main>
    </>
  );
}
