import React, { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useStore } from '../state/StoreContext.jsx';
import { formatINR, asset } from '../utils/legacy.js';
import '../styles/portal.css';
import PortalScope from '../components/PortalScope.jsx';
import { IconHome, IconLogin, IconPackage, IconReceipt, IconSearchScan, IconShield, IconTruck, IconUser } from '../components/LineIcons.jsx';

/* ==========================================================================
   OrdersPage — live loom-to-door tracking
   --------------------------------------------------------------------------
   The same two-column workspace as the static build: account and filters on
   the left, one card per order on the right with a five-stage tracker, the
   delivery record, the Razorpay / COD breakdown, and an inline review form that writes
   straight into the same reviews key the seller portal reads.

   Filtering and searching were a full re-render of a string of markup; here
   they are two pieces of state and a derived list.
   ========================================================================== */

const ORDER_STAGES = [
  { label: 'Order Confirmed', desc: 'Confirmed via HunarLink Checkout' },
  { label: 'GI Seal Verified', desc: 'Lab purity & laser QR sealed' },
  { label: 'Packed at Loom', desc: 'Insured Kashmiri heirloom box' },
  { label: 'Out for Delivery', desc: 'Tracked insured transit' },
  { label: 'Delivered', desc: 'Verified by Buyer' }
];

/* Image paths arrive from three places — seeded orders, the checkout wizard and
   the seller portal — so they come in as bare asset paths, absolute paths, or
   full URLs. Resolve all three. */
const resolveImg = (src) => {
  if (!src) return asset('assets/image_1.jpg');
  if (/^https?:|^data:/.test(src)) return src;
  return asset(String(src).replace(/^\/+/, ''));
};

export default function OrdersPage() {
  const { user, orders, addReview, advanceOrder, toast } = useStore();
  const [filter, setFilter] = useState('all');
  const [query, setQuery] = useState('');
  const [drafts, setDrafts] = useState({});

  const signedIn = Boolean(user && user.isLoggedIn !== false);

  const visible = useMemo(() => {
    let list = orders;
    if (filter === 'ontheway') list = list.filter((o) => (o.stage || 1) < 5);
    else if (filter === 'delivered') list = list.filter((o) => (o.stage || 1) >= 5);

    const q = query.trim().toLowerCase();
    if (q) {
      list = list.filter(
        (o) =>
          (o.id || '').toLowerCase().includes(q) ||
          (o.address || '').toLowerCase().includes(q) ||
          (o.items || []).some(
            (i) =>
              (i.title || '').toLowerCase().includes(q) ||
              (i.giId || '').toLowerCase().includes(q) ||
              (i.artisan || '').toLowerCase().includes(q)
          )
      );
    }
    return list;
  }, [orders, filter, query]);

  const submitReview = (e, order) => {
    e.preventDefault();
    const id = order.id;
    const d = drafts[id] || {};
    if (!d.text || !d.text.trim()) return;
    const productId = order.items?.[0]?.productId || 'craft-item';
    addReview(productId, {
      author: user?.fullName || user?.name || user?.email || 'Verified Buyer',
      rating: Number(d.rating) || 5,
      date: new Date().toLocaleDateString('en-IN', {
        day: '2-digit',
        month: 'short',
        year: 'numeric'
      }),
      comment: d.text.trim()
    });
    setDrafts((prev) => ({ ...prev, [id]: { ...prev[id], text: '' } }));
    toast("\u2605 Review submitted & synced directly to the artisan's Seller Portal!", 'success');
  };

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
              <div className="up-brand-sub">Live Order Tracking</div>
            </div>
          </Link>
          <nav className="up-nav-links">
            <Link to="/" className="up-nav-pill">
              <IconHome size={15} /> Storefront
            </Link>
            <Link to="/profile" className="up-nav-pill">
              <IconUser size={15} /> My Profile
            </Link>
            <Link to="/orders" className="up-nav-pill active">
              <IconPackage size={15} /> Track Orders
            </Link>
            {!signedIn && (
              <Link to="/login" className="up-nav-pill" id="nav-auth-pill">
                <IconLogin size={15} /> Sign in
              </Link>
            )}
          </nav>
        </div>
      </header>

      <main className="up-container" id="main-content">

        <h1 className="up-page-h1">Live Order Tracking</h1>
        <div className="orders-layout">
          <aside className="orders-filter-card">
            <div
              style={{
                paddingBottom: 14,
                marginBottom: 14,
                borderBottom: '1px solid var(--border-light)'
              }}
            >
              <div
                style={{
                  fontSize: '0.7rem',
                  fontWeight: 800,
                  textTransform: 'uppercase',
                  letterSpacing: '0.08em',
                  color: 'var(--text-500)',
                  marginBottom: 6
                }}
              >
                User Account
              </div>

              {signedIn ? (
                <div id="trk-identity">
                  <div
                    style={{
                      fontFamily: 'var(--font-serif)',
                      fontSize: '1.25rem',
                      fontWeight: 700,
                      color: 'var(--heading-color)'
                    }}
                    id="trk-user-name"
                  >
                    {user?.fullName || user?.name || 'Verified Buyer'}
                  </div>
                  <div style={{ fontSize: '0.76rem', color: 'var(--text-700)' }} id="trk-user-contact">
                    {user?.email || ''}
                  </div>
                  <Link
                    to="/profile"
                    className="btn-link-edit"
                    style={{ display: 'inline-block', paddingLeft: 0, marginTop: 6 }}
                  >
                    &#9999;&#65039; Customize Profile &rarr;
                  </Link>
                </div>
              ) : (
                <div id="trk-signed-out">
                  <div
                    style={{
                      fontFamily: 'var(--font-serif)',
                      fontSize: '1.15rem',
                      fontWeight: 700,
                      color: 'var(--heading-color)'
                    }}
                  >
                    Not signed in
                  </div>
                  <p
                    style={{
                      fontSize: '0.76rem',
                      color: 'var(--text-700)',
                      lineHeight: 1.5,
                      margin: '6px 0 10px'
                    }}
                  >
                    Sign in to see your own orders and live loom-to-door tracking.
                  </p>
                  <Link
                    to="/login"
                    className="btn-orange"
                    style={{ width: '100%', justifyContent: 'center' }}
                  >
                    <IconLogin size={15} /> Sign in to view orders
                  </Link>
                </div>
              )}
            </div>

            <h3 style={{ fontSize: '1.15rem', marginBottom: 12 }}>Filters</h3>

            <div style={{ marginBottom: 16 }}>
              <div
                style={{
                  fontSize: '0.72rem',
                  fontWeight: 800,
                  textTransform: 'uppercase',
                  letterSpacing: '0.06em',
                  color: 'var(--text-500)',
                  marginBottom: 8
                }}
              >
                ORDER STATUS
              </div>
              {[
                { v: 'all', label: 'All Orders' },
                { v: 'ontheway', label: 'On the Way' },
                { v: 'delivered', label: 'Delivered' }
              ].map((o) => (
                <label
                  className="gender-radio-label"
                  key={o.v}
                  style={{ display: 'flex', marginBottom: 8 }}
                >
                  <input
                    type="radio"
                    name="status-filter"
                    value={o.v}
                    checked={filter === o.v}
                    onChange={() => setFilter(o.v)}
                  />{' '}
                  {o.label}
                </label>
              ))}
            </div>
          </aside>

          <section>
            <div className="orders-search-bar">
              <input
                type="text"
                id="orders-search-input" aria-label="Search your orders"
                className="up-input"
                placeholder="Search your orders by Order ID, craft title, artisan, or GI ID..."
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
              <button type="button" className="btn-orange">
                <IconSearchScan size={15} /> Search Orders
              </button>
            </div>

            <div id="orders-list-wrap">
              {!signedIn ? (
                <div className="fk-panel-card" style={{ textAlign: 'center', padding: '42px 20px' }}>
                  <div style={{ fontSize: '2.2rem', marginBottom: 8 }}><IconUser size={15} /></div>
                  <h3>Sign in to view your orders</h3>
                  <p style={{ fontSize: '0.84rem', color: 'var(--text-500)', margin: '6px 0 18px' }}>
                    Orders are tied to your verified account, so they are hidden while you are
                    signed out.
                  </p>
                  <Link to="/login" className="btn-orange">
                    <IconLogin size={15} /> Sign in
                  </Link>
                </div>
              ) : visible.length === 0 ? (
                <div className="fk-panel-card" style={{ textAlign: 'center', padding: '42px 20px' }}>
                  <div style={{ fontSize: '2.2rem', marginBottom: 8 }}><IconPackage size={15} /></div>
                  <h3>No orders placed yet</h3>
                  <p style={{ fontSize: '0.84rem', color: 'var(--text-500)', margin: '6px 0 18px' }}>
                    Orders you place at Checkout are stored live in HunarLink&rsquo;s database and
                    tracked right here from workshop to door.
                  </p>
                  <div
                    style={{ display: 'flex', gap: 10, justifyContent: 'center', flexWrap: 'wrap' }}
                  >
                    <Link to="/#marketplace-section" className="btn-orange">
                      Explore Verified Crafts &rarr;
                    </Link>
                  </div>
                </div>
              ) : (
                visible.map((o) => (
                  <OrderCard
                    key={o.id}
                    order={o}
                    user={user}
                    draft={drafts[o.id] || {}}
                    onDraft={(patch) =>
                      setDrafts((p) => ({ ...p, [o.id]: { ...(p[o.id] || {}), ...patch } }))
                    }
                    onAdvance={() => advanceOrder(o.id)}
                    onReview={(e) => submitReview(e, o)}
                  />
                ))
              )}
            </div>
          </section>
        </div>
      </main>

      <div className="up-toast" id="up-toast" />
    </>
  );
}

function OrderCard({ order: o, user, draft, onDraft, onAdvance, onReview }) {
  const stage = Math.max(1, Math.min(5, o.stage || 1));
  const stageInfo = ORDER_STAGES[stage - 1];
  const b = o.buyer || {};
  const buyerName = b.name || user?.fullName || user?.name || 'Verified Buyer';
  const buyerPhone = b.phone || user?.phone || '';
  const buyerEmail = b.email || user?.email || '';
  const buyerAddr = b.locality
    ? `${b.locality}, ${b.city || ''}${b.pincode ? ` - ${b.pincode}` : ''}`
    : o.address || 'Verified Delivery Address';
  const subtotal = o.subtotal || o.total || 0;
  const discount = o.discount || 0;

  return (
    <article className="fk-order-card">
      <div className="fk-order-top">
        <div>
          <div className="fk-order-id">Order #{o.id}</div>
          <div style={{ fontSize: '0.76rem', color: 'var(--text-500)' }}>
            Ordered on <strong>{o.date || 'Recent'}</strong>
            {o.time ? ` at ${o.time}` : ''} &bull;{' '}
            <strong>{o.paymentMethod || 'Razorpay Standard Checkout'}</strong>
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          <span
            style={{
              fontSize: '0.74rem',
              fontWeight: 700,
              padding: '5px 12px',
              borderRadius: 999,
              background: stage >= 5 ? 'var(--success-50)' : 'var(--btn-orange-soft)',
              color: stage >= 5 ? 'var(--success-600)' : 'var(--heading-color)',
              border: `1px solid ${stage >= 5 ? '#BFE3CE' : 'var(--btn-orange-border)'}`
            }}
          >
            &#9679; {stageInfo.label}
          </span>
          <button
            type="button"
            className="btn-orange-outline"
            style={{ padding: '6px 12px', fontSize: '0.74rem' }}
            onClick={() => window.print()}
          >
            <IconReceipt size={15} /> GI Invoice
          </button>
        </div>
      </div>

      <div className="fk-order-body">
        <div>
          {(o.items || []).map((item, i) => (
            <div className="fk-item-row" key={`${o.id}-${item.productId || i}`}>
              <img
                src={resolveImg(item.image)}
                className="fk-item-thumb"
                alt={item.title}
              />
              <div style={{ flex: 1, minWidth: 0 }}>
                <Link
                  to={`/product?id=${encodeURIComponent(item.productId || 'hl-pash-001')}`}
                  style={{
                    fontWeight: 700,
                    color: 'var(--heading-color)',
                    textDecoration: 'none',
                    fontSize: '0.9rem'
                  }}
                >
                  {item.title}
                </Link>
                <div style={{ fontSize: '0.74rem', color: 'var(--text-500)', marginTop: 2 }}>
                  Qty: <strong>{item.qty || 1}</strong> &bull; GI Tag:{' '}
                  <code>{item.giId || 'GI-VERIFIED'}</code>
                  {item.artisan ? ` \u2022 By ${item.artisan}` : ''}
                </div>
              </div>
              <div style={{ fontWeight: 800, color: 'var(--text-900)', fontSize: '0.92rem' }}>
                {formatINR(item.lineTotal || item.price * (item.qty || 1))}
              </div>
            </div>
          ))}

          <div className="fk-tracker-wrap">
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                marginBottom: 12,
                flexWrap: 'wrap',
                gap: 6
              }}
            >
              <span
                style={{
                  fontSize: '0.74rem',
                  fontWeight: 800,
                  textTransform: 'uppercase',
                  letterSpacing: '0.06em',
                  color: 'var(--heading-color)'
                }}
              >
                <IconTruck size={15} /> Live Shipment Status &mdash; {stageInfo.desc}
              </span>
              {stage < 5 ? (
                <button type="button" className="btn-link-edit" onClick={onAdvance}>
                  Simulate Next Stage &rarr;
                </button>
              ) : (
                <span
                  style={{ fontSize: '0.74rem', fontWeight: 700, color: 'var(--success-600)' }}
                >
                  &#10003; Delivered Successfully
                </span>
              )}
            </div>
            <div className="fk-tracker-steps">
              {ORDER_STAGES.map((st, idx) => {
                const sNum = idx + 1;
                const done = sNum <= stage;
                const current = sNum === stage;
                return (
                  <div
                    className={`fk-step${done ? ' done' : ''}${current ? ' current' : ''}`}
                    key={st.label}
                  >
                    <div className="fk-step-dot">{done ? '\u2713' : sNum}</div>
                    <div className="fk-step-label">{st.label}</div>
                  </div>
                );
              })}
            </div>
          </div>

          {o.sellerNote ? (
            <div className="seller-note-banner">
              <strong> Live Update from Artisan Workshop:</strong> {o.sellerNote}
            </div>
          ) : null}

          <form
            onSubmit={onReview}
            style={{
              display: 'flex',
              gap: 8,
              flexWrap: 'wrap',
              alignItems: 'center',
              marginTop: 8
            }}
          >
            <select
              className="up-select"
              style={{ width: 'auto', padding: '8px 10px', fontSize: '0.78rem' }}
              value={draft.rating || '5'}
              onChange={(e) => onDraft({ rating: e.target.value })}
              aria-label="Rating"
            >
              <option value="5">5 stars</option>
              <option value="4">4 stars</option>
              <option value="3">3 stars</option>
            </select>
            <input
              type="text"
              className="up-input"
              style={{ flex: '1 1 200px', padding: '8px 12px', fontSize: '0.8rem' }}
              placeholder="Rate & review this Kashmiri craft for the artisan..."
              required
              value={draft.text || ''}
              onChange={(e) => onDraft({ text: e.target.value })}
            />
            <button
              type="submit"
              className="btn-orange"
              style={{ padding: '8px 14px', fontSize: '0.78rem' }}
            >
              Submit Review
            </button>
          </form>
        </div>

        <div className="fk-info-sidebar">
          <div className="fk-info-box">
            <h4><IconUser size={15} /> Delivery &amp; User Information</h4>
            <div style={{ fontWeight: 700, color: 'var(--text-900)', marginBottom: 3 }}>
              {buyerName}
              <span className="addr-type-chip" style={{ marginLeft: 6 }}>
                {b.addressType || 'Home'}
              </span>
            </div>
            <div style={{ color: 'var(--text-700)', marginBottom: 6 }}>{buyerAddr}</div>
            <div style={{ fontSize: '0.76rem', color: 'var(--text-700)' }}>
              <div>
                <strong>Phone:</strong> {buyerPhone}
              </div>
              <div>
                <strong>Email:</strong> {buyerEmail}
              </div>
            </div>
          </div>

          <div className="fk-info-box">
            <h4><IconReceipt size={15} /> Price &amp; Payment Details</h4>
            <div className="fk-price-line">
              <span>Craft Subtotal</span>
              <span>{formatINR(subtotal)}</span>
            </div>
            {discount > 0 && (
              <div className="fk-price-line" style={{ color: 'var(--success-600)' }}>
                <span>Coupon / Guild Savings</span>
                <span>&minus; {formatINR(discount)}</span>
              </div>
            )}
            <div className="fk-price-line">
              <span>Insured Transit Shipping</span>
              <span style={{ color: 'var(--success-600)', fontWeight: 700 }}>FREE</span>
            </div>
            <div className="fk-price-line total">
              <span>Total Paid</span>
              <span>{formatINR(o.total)}</span>
            </div>
            <div
              style={{
                fontSize: '0.72rem',
                color: 'var(--success-600)',
                fontWeight: 700,
                marginTop: 6
              }}
            >
              <IconShield size={15} /> {o.paymentStatus || 'Verified by Razorpay Checkout'}
            </div>
          </div>
        </div>
      </div>
    </article>
  );
}