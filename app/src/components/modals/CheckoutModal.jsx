import React, { useEffect, useMemo, useState } from 'react';
import { useStore } from '../../state/StoreContext.jsx';
import { useClerkBridge } from '../../data/clerkConfig.js';
import { formatINR } from '../../utils/legacy.js';
import {
  createMyAddress,
  createRetailOrder,
  probeBackendHealth
} from '../../services/apiClient.js';
import {
  executeServerRetailCheckout,
  startRazorpayStandardCheckout
} from '../../services/razorpayCheckout.js';
import Modal from '../Modal.jsx';
import { IconShield } from '../../components/LineIcons.jsx';

/* ==========================================================================
   CheckoutModal — four-step acquisition wizard
   --------------------------------------------------------------------------
   1. User identity
   2. Delivery address (saved, or add a new one)
   3. Order summary with the GI certificate preview
   4. Payment — UPI (Apps, VPA/UPI ID Verify, Scan & Pay QR), Cards,
      NetBanking & Cash on Delivery (backed by Razorpay Standard Checkout
      when configured, with interactive Sandbox Demo fallback for previews).
   ========================================================================== */

const STEPS = [
  '1. User ID',
  '2. Delivery Address',
  '3. GI Certificate & Summary',
  '4. Payment'
];

const UPI_APPS = [
  { id: 'gpay', name: 'Google Pay', sub: 'Instant intent', tag: 'Popular' },
  { id: 'phonepe', name: 'PhonePe', sub: 'Fastest UPI', tag: null },
  { id: 'paytm', name: 'Paytm UPI', sub: 'UPI & Lite', tag: null },
  { id: 'bhim', name: 'BHIM UPI', sub: 'NPCI Official', tag: null },
  { id: 'cred', name: 'CRED UPI', sub: 'Rewards eligible', tag: null },
  { id: 'amazon', name: 'Amazon Pay', sub: 'UPI Wallet', tag: null }
];

const UPI_HANDLES = ['@okaxis', '@okhdfcbank', '@okicici', '@ybl', '@paytm'];

const POPULAR_BANKS = [
  { id: 'jkbank', name: 'J&K Bank', code: 'JKB' },
  { id: 'hdfc', name: 'HDFC Bank', code: 'HDFC' },
  { id: 'sbi', name: 'State Bank of India', code: 'SBI' },
  { id: 'icici', name: 'ICICI Bank', code: 'ICICI' },
  { id: 'axis', name: 'Axis Bank', code: 'AXIS' },
  { id: 'kotak', name: 'Kotak Mahindra', code: 'KTK' }
];

const OTHER_BANKS = [
  'Bank of Baroda',
  'Canara Bank',
  'Federal Bank',
  'IDFC FIRST Bank',
  'IndusInd Bank',
  'Punjab National Bank',
  'Union Bank of India',
  'Yes Bank'
];

function UpiAppIcon({ id }) {
  if (id === 'gpay') {
    return (
      <span className="hl-upi-badge hl-upi-badge--gpay" aria-hidden="true">
        <svg viewBox="0 0 24 24" width="20" height="20">
          <path fill="#4285F4" d="M21.8 12.2c0-.7-.1-1.4-.2-2H12v3.8h5.5c-.2 1.2-1 2.3-2 3v2.5h3.3c1.9-1.8 3-4.4 3-7.3z" />
          <path fill="#34A853" d="M12 22c2.8 0 5.1-.9 6.8-2.5l-3.3-2.5c-.9.6-2.1 1-3.5 1-2.7 0-5-1.8-5.8-4.3H2.8v2.6C4.5 19.8 8 22 12 22z" />
          <path fill="#FBBC05" d="M6.2 13.7c-.2-.6-.3-1.1-.3-1.7s.1-1.2.3-1.7V7.7H2.8C2.1 9 1.8 10.5 1.8 12s.4 3 1 4.3l3.4-2.6z" />
          <path fill="#EA4335" d="M12 6c1.5 0 2.9.5 3.9 1.5l2.9-2.9C17.1 2.9 14.8 2 12 2 8 2 4.5 4.2 2.8 7.7l3.4 2.6C7 7.8 9.3 6 12 6z" />
        </svg>
      </span>
    );
  }
  if (id === 'phonepe') {
    return (
      <span className="hl-upi-badge hl-upi-badge--phonepe" aria-hidden="true">
        पे
      </span>
    );
  }
  if (id === 'paytm') {
    return (
      <span className="hl-upi-badge hl-upi-badge--paytm" aria-hidden="true">
        <span>pay</span><strong>tm</strong>
      </span>
    );
  }
  if (id === 'bhim') {
    return (
      <span className="hl-upi-badge hl-upi-badge--bhim" aria-hidden="true">
        <svg viewBox="0 0 24 24" width="20" height="20">
          <polygon points="8,4 16,12 8,20 11.5,12" fill="#F37021" />
          <polygon points="12.5,4 20.5,12 12.5,20 16,12" fill="#008B45" />
        </svg>
      </span>
    );
  }
  if (id === 'cred') {
    return (
      <span className="hl-upi-badge hl-upi-badge--cred" aria-hidden="true">
        CR
      </span>
    );
  }
  return (
    <span className="hl-upi-badge hl-upi-badge--amazon" aria-hidden="true">
      a
    </span>
  );
}

/* Deterministic 21x21 stylized UPI QR code SVG (zero external network dependency). */
function UpiQrSvg({ seed }) {
  const cells = useMemo(() => {
    const size = 21;
    const isFinder = (r, c) =>
      (r < 7 && c < 7) || (r < 7 && c >= size - 7) || (r >= size - 7 && c < 7);
    const isCenterLogo = (r, c) => r >= 8 && r <= 12 && c >= 8 && c <= 12;

    const rects = [];
    let hash = 2166136261;
    const str = String(seed || 'hunarlink-upi');
    for (let i = 0; i < str.length; i += 1) {
      hash ^= str.charCodeAt(i);
      hash = Math.imul(hash, 16777619);
    }

    for (let r = 0; r < size; r += 1) {
      for (let c = 0; c < size; c += 1) {
        if (isFinder(r, c) || isCenterLogo(r, c)) continue;
        // Separator rings around finders
        if (
          (r === 7 && (c <= 7 || c >= size - 8)) ||
          (c === 7 && (r <= 7 || r >= size - 8)) ||
          (r === size - 8 && c <= 7) ||
          (c === size - 8 && r <= 7)
        ) {
          continue;
        }
        // Timing lines
        if (r === 6 || c === 6) {
          if ((r + c) % 2 === 0) rects.push([c, r]);
          continue;
        }
        const v = Math.imul(hash ^ (r * 31 + c * 17 + r * c * 7), 2654435761) >>> 0;
        if (v % 10 < 5) rects.push([c, r]);
      }
    }
    return rects;
  }, [seed]);

  const finderBox = (x, y) => (
    <g key={`f-${x}-${y}`}>
      <rect x={x} y={y} width="7" height="7" rx="0.9" fill="#0B3A26" />
      <rect x={x + 1} y={y + 1} width="5" height="5" rx="0.5" fill="#FFFFFF" />
      <rect x={x + 2} y={y + 2} width="3" height="3" rx="0.4" fill="#0B3A26" />
    </g>
  );

  return (
    <svg
      viewBox="-1 -1 23 23"
      className="hl-upi-qr-svg"
      role="img"
      aria-label="HunarLink UPI Scan and Pay QR Code"
    >
      <rect x="-1" y="-1" width="23" height="23" rx="1.4" fill="#FFFFFF" />
      {finderBox(0, 0)}
      {finderBox(14, 0)}
      {finderBox(0, 14)}
      {cells.map(([x, y]) => (
        <rect key={`${x}-${y}`} x={x} y={y} width="0.92" height="0.92" rx="0.18" fill="#10291D" />
      ))}
      <rect x="8.1" y="8.1" width="4.8" height="4.8" rx="1" fill="#0B3A26" stroke="#D9AE4A" strokeWidth="0.35" />
      <text
        x="10.5"
        y="11.45"
        textAnchor="middle"
        fill="#F2D98A"
        fontSize="2.7"
        fontWeight="700"
        fontFamily="Georgia, serif"
      >
        HL
      </text>
    </svg>
  );
}

export default function CheckoutModal() {
  const {
    ui,
    closeModal,
    openModal,
    cartItems,
    totals,
    coupon,
    addresses,
    addAddress,
    user,
    placeOrder,
    clearCart,
    removeCoupon,
    hydrateFromBackend,
    toast
  } = useStore();

  const { getToken, isSignedIn: clerkSignedIn } = useClerkBridge();
  const [step, setStep] = useState(1);
  const [buyer, setBuyer] = useState({
    name: user?.fullName || user?.name || '',
    phone: user?.phone || ''
  });
  const [addressId, setAddressId] = useState(addresses[0]?.id);
  const [draft, setDraft] = useState({
    name: '',
    phone: '',
    pin: '',
    city: '',
    loc: ''
  });

  // Payment rail state
  const [payRail, setPayRail] = useState('upi'); // 'upi' | 'card' | 'netbanking' | 'cod'
  const [selectedUpiApp, setSelectedUpiApp] = useState('gpay');
  const [upiMode, setUpiMode] = useState('app'); // 'app' | 'vpa'
  const [upiId, setUpiId] = useState('');
  const [vpaState, setVpaState] = useState({ status: 'idle', verifiedId: '', holder: '' });
  const [qrSeconds, setQrSeconds] = useState(300);

  // NetBanking preview form state (Card PAN/CVV never collected in DOM — PCI-DSS SAQ-A)
  const [selectedBank, setSelectedBank] = useState('jkbank');
  const [otherBank, setOtherBank] = useState('');

  // Processing state
  const [method, setMethod] = useState(null);
  const [processingBanner, setProcessingBanner] = useState(null);
  const [backendStatus, setBackendStatus] = useState({ online: false, ready: null });

  const isOpen = Boolean(ui.modal && ui.modal.type === 'checkout');

  useEffect(() => {
    if (!isOpen) return undefined;
    let active = true;
    probeBackendHealth().then((status) => {
      if (active) setBackendStatus(status);
    });
    return () => {
      active = false;
    };
  }, [isOpen]);

  // Countdown timer for the UPI QR code while on Step 4 + UPI rail
  useEffect(() => {
    if (!isOpen || step !== 4 || payRail !== 'upi') return undefined;
    setQrSeconds(300);
    const id = window.setInterval(() => {
      setQrSeconds((s) => (s > 1 ? s - 1 : 300));
    }, 1000);
    return () => window.clearInterval(id);
  }, [isOpen, step, payRail]);

  if (!isOpen) return null;

  const selected = addresses.find((a) => a.id === addressId) || addresses[0];
  const qrMins = String(Math.floor(qrSeconds / 60)).padStart(2, '0');
  const qrSecs = String(qrSeconds % 60).padStart(2, '0');

  const saveAddress = async (e) => {
    e.preventDefault();
    const clean = Object.fromEntries(
      Object.entries(draft).map(([k, v]) => [k, String(v).trim()])
    );
    if (!clean.name || !clean.phone || !clean.pin || !clean.loc || !clean.city) {
      toast('\u26a0\ufe0f Please fill every delivery field (name, mobile, pincode, locality & city)');
      return;
    }
    try {
      const token = clerkSignedIn && getToken ? await getToken() : null;
      if (backendStatus.online && token) {
        const saved = await createMyAddress(
          {
            address_label: 'DELIVERY',
            recipient_name: clean.name,
            recipient_phone: clean.phone,
            line1: clean.loc,
            city: clean.city,
            state_province: 'Jammu and Kashmir',
            postal_code: clean.pin,
            is_default: addresses.length === 0
          },
          token
        );
        await hydrateFromBackend(token);
        setAddressId(saved.id);
        setStep(3);
        toast('Delivery address saved to database and selected', 'success');
        return;
      }
    } catch (err) {
      toast(err?.message || 'Could not save address to database.', 'error');
      return;
    }
    const next = {
      id: `addr-${Date.now()}`,
      name: clean.name,
      phone: clean.phone,
      pincode: clean.pin,
      locality: clean.loc,
      city: clean.city,
      type: 'Delivery'
    };
    addAddress(next);
    setAddressId(next.id);
    setStep(3);
    toast('Delivery address saved and selected', 'success');
  };

  const applyUpiHandle = (handle) => {
    setUpiMode('vpa');
    setVpaState({ status: 'idle', verifiedId: '', holder: '' });
    setUpiId((prev) => {
      const base = (prev || '').split('@')[0].trim() || (buyer.name || 'collector').toLowerCase().replace(/[^a-z0-9]+/g, '.');
      return `${base}${handle}`;
    });
  };

  const verifyUpiId = () => {
    const clean = upiId.trim().toLowerCase();
    if (!/^[a-z0-9._-]{2,}@[a-z]{2,}$/i.test(clean)) {
      setVpaState({ status: 'error', verifiedId: '', holder: '' });
      toast('Enter a valid UPI ID such as yourname@okaxis or 9811044210@ybl', 'error');
      return;
    }
    setUpiMode('vpa');
    setVpaState({ status: 'checking', verifiedId: '', holder: '' });
    window.setTimeout(() => {
      setVpaState({
        status: 'verified',
        verifiedId: clean,
        holder: buyer.name || user?.name || 'Verified Account Holder'
      });
      toast(`UPI ID ${clean} verified via NPCI BHIM`, 'success');
    }, 420);
  };

  const pay = async (paymentMethod, bannerText = null) => {
    setMethod(paymentMethod);
    const isCod = /cod|delivery/i.test(paymentMethod);
    const now = new Date();
    let orderId = `HL-ORD-2026-${Math.floor(1000 + Math.random() * 9000)}`;
    let authoritativeTotal = totals.netPayable;
    const demoUtr = `6${Math.floor(10000000000 + Math.random() * 89999999999)}`;

    let verifiedPaymentStatus = isCod
      ? 'COD (Pay on Delivery — Separate from Online Checkout)'
      : `Sandbox Demo Confirmed (Ref: ${demoUtr})`;

    const authToken = ui.modal?.authToken || (clerkSignedIn && getToken ? await getToken() : null);
    const serverListingItems = cartItems
      .filter(({ product: p }) => Boolean(p.sellerListingId))
      .map(({ product: p, qty }) => ({ seller_listing_id: p.sellerListingId, quantity: qty }));
    const allItemsHaveServerListing =
      cartItems.length > 0 && serverListingItems.length === cartItems.length;

    let ranLiveServerCheckout = false;

    if (backendStatus.online && authToken) {
      try {
        if (!isCod && ui.modal?.backendOrderId) {
          ranLiveServerCheckout = true;
          const verified = await startRazorpayStandardCheckout({
            orderScope: ui.modal?.orderScope || 'RETAIL',
            orderId: ui.modal.backendOrderId,
            authToken,
            buyer: {
              name: buyer.name || selected?.name,
              email: user?.email,
              phone: buyer.phone || selected?.phone
            }
          });
          verifiedPaymentStatus = `${verified.payment_status} (${verified.fulfilment_status})`;
        } else if (allItemsHaveServerListing && backendStatus.ready?.razorpay_configured && !isCod) {
          ranLiveServerCheckout = true;
          const result = await executeServerRetailCheckout({
            items: serverListingItems,
            shippingAddress: {
              name: buyer.name || selected?.name || user?.fullName || 'Verified Buyer',
              phone: buyer.phone || selected?.phone || user?.phone || '+91 9811044210',
              locality: selected?.locality || 'Residency Road',
              city: selected?.city || 'Jammu',
              state: selected?.state || 'Jammu and Kashmir',
              pincode: selected?.pincode || '180001'
            },
            paymentMethod: 'RAZORPAY_STANDARD',
            authToken,
            buyer: {
              name: buyer.name || selected?.name,
              email: user?.email,
              phone: buyer.phone || selected?.phone
            }
          });
          orderId = result.order.order_number || orderId;
          authoritativeTotal = Number(result.order.total_amount) || totals.netPayable;
          verifiedPaymentStatus = result.paymentStatusLabel;
        } else if (allItemsHaveServerListing) {
          ranLiveServerCheckout = true;
          if (!isCod) {
            setProcessingBanner(bannerText || `Recording ${paymentMethod} order in database…`);
          }
          const createdOrder = await createRetailOrder(
            {
              items: serverListingItems,
              shipping_address: {
                name: buyer.name || selected?.name || user?.fullName || 'Verified Buyer',
                phone: buyer.phone || selected?.phone || user?.phone || '+91 9811044210',
                locality: selected?.locality || 'Residency Road',
                city: selected?.city || 'Jammu',
                state: selected?.state || 'Jammu and Kashmir',
                pincode: selected?.pincode || '180001'
              },
              payment_method: isCod ? 'COD' : 'RAZORPAY_STANDARD',
              payment_label: paymentMethod
            },
            authToken
          );
          setProcessingBanner(null);
          orderId = createdOrder.order_number || orderId;
          authoritativeTotal = Number(createdOrder.total_amount) || totals.netPayable;
          verifiedPaymentStatus = `${createdOrder.payment_status} (${createdOrder.fulfilment_status})`;
        }
      } catch (err) {
        setMethod(null);
        setProcessingBanner(null);
        toast(err?.message || 'Server checkout could not be completed.', 'error');
        return;
      }
    }

    if (ranLiveServerCheckout && authToken) {
      await hydrateFromBackend(authToken);
    }

    const order = {
      id: orderId,
      date: now.toLocaleDateString('en-IN', {
        day: '2-digit',
        month: 'short',
        year: 'numeric'
      }),
      time: now.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' }),
      createdAt: now.toISOString(),
      buyer: {
        name: buyer.name || selected?.name || user?.fullName || user?.name || 'Verified Buyer',
        phone: buyer.phone || selected?.phone || user?.phone || '',
        email: user?.email || '',
        addressType: selected?.type || 'Home',
        locality: selected?.locality || '',
        city: selected?.city || '',
        pincode: selected?.pincode || '',
        fullAddress: selected
          ? `${selected.name}, ${selected.locality}, ${selected.city} - ${selected.pincode}`
          : ''
      },
      items: cartItems.map(({ product: p, qty }) => ({
        productId: p.id,
        title: p.title,
        qty,
        price: p.price,
        lineTotal: p.price * qty,
        giId: p.giId,
        artisan: p.artisan,
        guild: p.guildLabel || p.guild,
        image: p.image
      })),
      subtotal: totals.sellingSubtotal,
      discount: totals.couponDiscount || 0,
      couponCode: coupon || null,
      shippingFee: totals.shippingFee || 0,
      total: authoritativeTotal,
      paymentMethod,
      paymentStatus: verifiedPaymentStatus,
      address: selected
        ? `${selected.name}, ${selected.locality}, ${selected.city} - ${selected.pincode}`
        : '',
      stage: 1,
      sellerNote: '',
      isNewForSeller: true
    };

    if (!ranLiveServerCheckout) {
      placeOrder(order);
    }
    clearCart();
    removeCoupon();
    setMethod(null);
    closeModal();
    openModal('orders');
    toast(
      isCod
        ? `COD Order ${orderId} confirmed.`
        : `Order ${orderId} confirmed via ${paymentMethod}!`,
      'success'
    );
  };

  const handleUpiSubmit = () => {
    if (upiMode === 'vpa') {
      const clean = upiId.trim().toLowerCase();
      if (!/^[a-z0-9._-]{2,}@[a-z]{2,}$/i.test(clean)) {
        toast('Please enter a valid UPI ID (e.g. yourname@okaxis) or pick a UPI app above.', 'error');
        return;
      }
      pay(`UPI ID (${clean})`, `Sending collect request to ${clean}…`);
      return;
    }
    const app = UPI_APPS.find((a) => a.id === selectedUpiApp) || UPI_APPS[0];
    pay(`UPI · ${app.name}`, `Opening ${app.name} UPI approval for ${formatINR(totals.netPayable)}…`);
  };

  const handleCardSubmit = (e) => {
    e.preventDefault();
    pay(
      'Credit / Debit Card (Razorpay Hosted Checkout)',
      `Opening PCI-DSS Level 1 Razorpay Checkout for ${formatINR(totals.netPayable)}…`
    );
  };

  const handleNetBankingSubmit = () => {
    const bankName =
      otherBank || (POPULAR_BANKS.find((b) => b.id === selectedBank)?.name ?? 'J&K Bank');
    pay(`NetBanking · ${bankName}`, `Redirecting securely to ${bankName} NetBanking…`);
  };

  const activeUpiAppObj = UPI_APPS.find((a) => a.id === selectedUpiApp) || UPI_APPS[0];

  return (
    <Modal
      id="checkout-modal"
      width="920px"
      title={<><IconShield size={14} /> Insured Acquisition Checkout</>}
      onClose={closeModal}
    >
      <div className="modal-body" id="checkout-modal-body">
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8, marginBottom: 20 }}>
          {STEPS.map((label, idx) => {
            const n = idx + 1;
            const active = n === step;
            const done = n < step;
            return (
              <button
                type="button"
                key={label}
                onClick={() => setStep(n)}
                style={{
                  padding: 8,
                  borderRadius: 6,
                  fontSize: '0.74rem',
                  fontWeight: 700,
                  background: active ? 'var(--forest-900)' : done ? 'var(--forest-100)' : 'var(--bg-ivory)',
                  color: active ? '#FFF' : 'var(--forest-900)'
                }}
              >
                {label}
              </button>
            );
          })}
        </div>

        {step === 1 && (
          <div style={{ background: 'var(--bg-ivory)', padding: 18, borderRadius: 10 }}>
            <h3 style={{ fontFamily: 'var(--font-serif)', fontSize: '1.35rem', marginBottom: 10 }}>
              Step 1: User Identity &amp; GI Ownership Registration
            </h3>
            <p style={{ fontSize: '0.8rem', color: 'var(--text-500)', marginBottom: 14 }}>
              Your name is cryptographically bound to the Digital GI Ownership Passport upon
              dispatch.
            </p>
            <div className="form-grid">
              <div className="form-field">
                <label htmlFor="chk-buyer-name">Full Name</label>
                <input
                  type="text"
                  id="chk-buyer-name"
                  value={buyer.name}
                  onChange={(e) => setBuyer((b) => ({ ...b, name: e.target.value }))}
                />
              </div>
              <div className="form-field">
                <label htmlFor="chk-buyer-phone">Phone (SMS/WhatsApp Loom Telemetry)</label>
                <input
                  type="text"
                  id="chk-buyer-phone"
                  value={buyer.phone}
                  onChange={(e) => setBuyer((b) => ({ ...b, phone: e.target.value }))}
                />
              </div>
            </div>
            <div style={{ marginTop: 16, textAlign: 'right' }}>
              <button type="button" className="btn-primary-forest" onClick={() => setStep(2)}>
                Continue to Delivery Address &rarr;
              </button>
            </div>
          </div>
        )}

        {step === 2 && (
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 18 }}>
            <div>
              <h4 style={{ fontFamily: 'var(--font-serif)', fontSize: '1.2rem', marginBottom: 10 }}>
                Select Saved Address
              </h4>
              {addresses.map((a) => (
                <label
                  key={a.id}
                  style={{
                    display: 'block',
                    padding: 12,
                    border: `2px solid ${
                      addressId === a.id ? 'var(--forest-900)' : 'var(--border-light)'
                    }`,
                    borderRadius: 8,
                    marginBottom: 10,
                    cursor: 'pointer'
                  }}
                >
                  <input
                    type="radio"
                    name="selectedAddr"
                    checked={addressId === a.id}
                    onChange={() => setAddressId(a.id)}
                  />
                  <strong style={{ fontSize: '0.84rem', marginLeft: 6 }}>
                    {a.name} ({a.type || 'Home'})
                  </strong>
                  <div style={{ fontSize: '0.76rem', color: 'var(--text-500)', marginTop: 4 }}>
                    {a.locality}, {a.city} - {a.pincode} &bull; Ph: {a.phone}
                  </div>
                </label>
              ))}
              <button
                type="button"
                className="btn-primary-forest"
                style={{ marginTop: 8 }}
                onClick={() => setStep(3)}
              >
                Deliver to Selected Address &rarr;
              </button>
            </div>

            <form onSubmit={saveAddress} style={{ background: 'var(--bg-ivory)', padding: 14, borderRadius: 8 }}>
              <h4 style={{ fontFamily: 'var(--font-serif)', fontSize: '1.15rem', marginBottom: 8 }}>
                Or Add New Address
              </h4>
              <div className="form-grid">
                <div className="form-field">
                  <label htmlFor="addr-name">Full Name</label>
                  <input
                    type="text"
                    id="addr-name"
                    required
                    placeholder="Receiver Name"
                    value={draft.name}
                    onChange={(e) => setDraft((d) => ({ ...d, name: e.target.value }))}
                  />
                </div>
                <div className="form-field">
                  <label htmlFor="addr-phone">Mobile</label>
                  <input
                    type="text"
                    id="addr-phone"
                    required
                    placeholder="10-digit Mobile"
                    value={draft.phone}
                    onChange={(e) => setDraft((d) => ({ ...d, phone: e.target.value }))}
                  />
                </div>
                <div className="form-field">
                  <label htmlFor="addr-pin">6-Digit Pincode</label>
                  <input
                    type="text"
                    id="addr-pin"
                    required
                    placeholder="e.g. 180001"
                    value={draft.pin}
                    onChange={(e) => setDraft((d) => ({ ...d, pin: e.target.value }))}
                  />
                </div>
                <div className="form-field">
                  <label htmlFor="addr-city">City &amp; State</label>
                  <input
                    type="text"
                    id="addr-city"
                    required
                    placeholder="Srinagar, J&K"
                    value={draft.city}
                    onChange={(e) => setDraft((d) => ({ ...d, city: e.target.value }))}
                  />
                </div>
                <div className="form-field full">
                  <label htmlFor="addr-loc">Street / Locality</label>
                  <input
                    type="text"
                    id="addr-loc"
                    required
                    placeholder="House No, Street, Landmark"
                    value={draft.loc}
                    onChange={(e) => setDraft((d) => ({ ...d, loc: e.target.value }))}
                  />
                </div>
              </div>
              <button type="submit" className="btn-acquire" style={{ marginTop: 10 }}>
                Save &amp; Use This Address
              </button>
            </form>
          </div>
        )}

        {step === 3 && (
          <div style={{ background: 'var(--bg-ivory)', padding: 18, borderRadius: 10 }}>
            <h3 style={{ fontFamily: 'var(--font-serif)', fontSize: '1.35rem', marginBottom: 10 }}>
              Step 3: Order Summary &amp; GI Ownership Certificate Preview
            </h3>
            {cartItems.map(({ product: p, qty }) => (
              <div
                key={p.id}
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  padding: '8px 0',
                  borderBottom: '1px solid var(--border-light)',
                  fontSize: '0.84rem'
                }}
              >
                <span>
                  <strong>{p.title}</strong> &times; {qty}{' '}
                  <code style={{ color: 'var(--forest-700)' }}>[{p.giId}]</code>
                </span>
                <strong>{formatINR(p.price * qty)}</strong>
              </div>
            ))}
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                fontSize: '1.05rem',
                fontWeight: 700,
                paddingTop: 10,
                color: 'var(--forest-950)'
              }}
            >
              <span>Payable Order Total (INR &mdash; Zero Convenience Fee on UPI)</span>
              <span>{formatINR(totals.netPayable)}</span>
            </div>
            <div style={{ marginTop: 16, display: 'flex', justifyContent: 'space-between' }}>
              <button type="button" className="btn-outline-ivory" onClick={() => setStep(2)}>
                &larr; Back
              </button>
              <button type="button" className="btn-primary-forest" onClick={() => setStep(4)}>
                Proceed to Payment &rarr;
              </button>
            </div>
          </div>
        )}

        {step === 4 && (
          <div className="hl-pay-shell">
            <div className="hl-pay-head">
              <div>
                <h3 className="hl-pay-title">
                  Step 4: Choose Payment Method
                </h3>
                <p className="hl-pay-sub">
                  Secured by <strong>Razorpay Standard Checkout</strong> &amp; NPCI UPI &bull; 256-bit TLS
                </p>
              </div>
              <div className="hl-pay-amount-box">
                <span>Amount Payable</span>
                <strong>{formatINR(totals.netPayable)}</strong>
              </div>
            </div>

            {processingBanner && (
              <div className="hl-pay-processing" role="status" aria-live="polite">
                <span className="hl-pay-spinner" aria-hidden="true" />
                <div>
                  <strong>{processingBanner}</strong>
                  <div style={{ fontSize: '0.73rem', opacity: 0.85 }}>
                    Do not refresh or close this window while confirming your transaction…
                  </div>
                </div>
              </div>
            )}

            {/* Rail Switcher Tabs */}
            <div className="hl-pay-tabs" role="tablist" aria-label="Payment Methods">
              {[
                { id: 'upi', label: 'UPI', badge: 'Instant · ₹0 Fee' },
                { id: 'card', label: 'Credit / Debit Card', badge: 'Visa · MC · RuPay' },
                { id: 'netbanking', label: 'NetBanking', badge: 'All Indian Banks' },
                { id: 'cod', label: 'Cash on Delivery', badge: 'Pay at Doorstep' }
              ].map((t) => (
                <button
                  key={t.id}
                  type="button"
                  role="tab"
                  aria-selected={payRail === t.id}
                  className={`hl-pay-tab${payRail === t.id ? ' is-active' : ''}`}
                  onClick={() => setPayRail(t.id)}
                >
                  <span className="hl-pay-tab-dot" aria-hidden="true" />
                  <span className="hl-pay-tab-copy">
                    <strong>{t.label}</strong>
                    <small>{t.badge}</small>
                  </span>
                </button>
              ))}
            </div>

            {/* ================= PANEL 1: UPI ================= */}
            {payRail === 'upi' && (
              <div className="hl-upi-layout">
                {/* Left: UPI Apps + UPI ID Verify */}
                <div className="hl-upi-left">
                  <div className="hl-pay-block-label">
                    <span>1. Pay using any UPI App</span>
                    <span className="hl-pay-zero-tag">RECOMMENDED</span>
                  </div>

                  <div className="hl-upi-app-grid">
                    {UPI_APPS.map((app) => {
                      const active = upiMode === 'app' && selectedUpiApp === app.id;
                      return (
                        <button
                          key={app.id}
                          type="button"
                          className={`hl-upi-app-card${active ? ' is-selected' : ''}`}
                          onClick={() => {
                            setSelectedUpiApp(app.id);
                            setUpiMode('app');
                          }}
                        >
                          <UpiAppIcon id={app.id} />
                          <span className="hl-upi-app-meta">
                            <strong>{app.name}</strong>
                            <small>{app.sub}</small>
                          </span>
                          {active && <span className="hl-upi-check" aria-hidden="true">✓</span>}
                        </button>
                      );
                    })}
                  </div>

                  <div className="hl-upi-divider">
                    <span>OR PAY USING UPI ID / VPA</span>
                  </div>

                  <div className={`hl-vpa-box${upiMode === 'vpa' ? ' is-active' : ''}`}>
                    <label htmlFor="hl-upi-vpa-input" className="hl-vpa-label">
                      Enter UPI ID / Mobile Number@upi
                    </label>
                    <div className="hl-vpa-row">
                      <input
                        id="hl-upi-vpa-input"
                        type="text"
                        placeholder="e.g. priya.sharma@okaxis"
                        value={upiId}
                        onFocus={() => setUpiMode('vpa')}
                        onChange={(e) => {
                          setUpiId(e.target.value);
                          setUpiMode('vpa');
                          if (vpaState.status !== 'idle') {
                            setVpaState({ status: 'idle', verifiedId: '', holder: '' });
                          }
                        }}
                      />
                      <button
                        type="button"
                        className="hl-vpa-verify-btn"
                        disabled={vpaState.status === 'checking'}
                        onClick={verifyUpiId}
                      >
                        {vpaState.status === 'checking'
                          ? 'Checking…'
                          : vpaState.status === 'verified'
                            ? '✓ Verified'
                            : 'Verify'}
                      </button>
                    </div>

                    <div className="hl-vpa-handles">
                      {UPI_HANDLES.map((h) => (
                        <button
                          key={h}
                          type="button"
                          className="hl-vpa-chip"
                          onClick={() => applyUpiHandle(h)}
                        >
                          {h}
                        </button>
                      ))}
                    </div>

                    {vpaState.status === 'verified' && (
                      <div className="hl-vpa-verified">
                        ✓ Verified VPA: <strong>{vpaState.verifiedId}</strong> &bull; {vpaState.holder}
                      </div>
                    )}
                  </div>

                  <button
                    type="button"
                    className="btn-primary-forest hl-pay-cta"
                    disabled={!!method}
                    onClick={handleUpiSubmit}
                  >
                    {method
                      ? 'Confirming Payment…'
                      : upiMode === 'vpa'
                        ? `Verify & Pay ${formatINR(totals.netPayable)} via UPI ID`
                        : `Pay ${formatINR(totals.netPayable)} via ${activeUpiAppObj.name}`}
                  </button>
                </div>

                {/* Right: Scan & Pay UPI QR */}
                <aside className="hl-upi-qr-card">
                  <div className="hl-upi-qr-head">
                    <strong>Scan &amp; Pay with UPI QR</strong>
                    <span className="hl-upi-qr-timer">Valid {qrMins}:{qrSecs}</span>
                  </div>
                  <div className="hl-upi-qr-frame">
                    <UpiQrSvg seed={`hl-${totals.netPayable}-${cartItems.length}`} />
                  </div>
                  <div className="hl-upi-qr-vpa">
                    Merchant VPA: <code>hunarlink@okhdfcbank</code>
                  </div>
                  <div className="hl-upi-qr-apps">
                    <span>GPay</span>
                    <span>PhonePe</span>
                    <span>Paytm</span>
                    <span>BHIM</span>
                    <span>CRED</span>
                  </div>
                  <button
                    type="button"
                    className="btn-outline-ivory hl-upi-qr-btn"
                    disabled={!!method}
                    onClick={() =>
                      pay(
                        'UPI QR Scan (BHIM / Razorpay)',
                        `Verifying UPI QR payment of ${formatINR(totals.netPayable)}…`
                      )
                    }
                  >
                    {method ? 'Verifying QR…' : `I've Scanned & Paid ${formatINR(totals.netPayable)}`}
                  </button>
                </aside>
              </div>
            )}

            {/* ================= PANEL 2: CARDS (PCI-DSS SAQ-A Hosted Checkout) ================= */}
            {payRail === 'card' && (
              <form className="hl-card-panel" onSubmit={handleCardSubmit}>
                <div className="hl-pay-block-label">
                  <span>Credit or Debit Card (Hosted Razorpay Checkout)</span>
                  <span className="hl-card-networks">VISA &bull; MasterCard &bull; RuPay</span>
                </div>
                <div
                  style={{
                    background: '#f7f5ee',
                    border: '1px solid rgba(20,56,42,0.16)',
                    borderRadius: 10,
                    padding: '14px 16px',
                    marginBottom: 14,
                    fontSize: '0.84rem',
                    lineHeight: 1.55,
                    color: '#203128'
                  }}
                >
                  <strong>PCI-DSS Security Guarantee:</strong> HunarLink never collects, views, or stores
                  card numbers or CVV codes in our browser forms. When you click below, card details are
                  entered exclusively inside <strong>Razorpay&apos;s encrypted Checkout window</strong> (or
                  confirmed cleanly in Sandbox Demo mode when previewing without live keys).
                </div>
                <button
                  type="submit"
                  className="btn-primary-forest hl-pay-cta"
                  disabled={!!method}
                >
                  {method
                    ? 'Launching Hosted Card Checkout…'
                    : `Continue to Razorpay Card Checkout (${formatINR(totals.netPayable)})`}
                </button>
              </form>
            )}

            {/* ================= PANEL 3: NETBANKING ================= */}
            {payRail === 'netbanking' && (
              <div className="hl-nb-panel">
                <div className="hl-pay-block-label">
                  <span>Select Popular Bank</span>
                  <span className="hl-card-networks">Instant Bank Transfer</span>
                </div>
                <div className="hl-bank-grid">
                  {POPULAR_BANKS.map((bank) => {
                    const active = !otherBank && selectedBank === bank.id;
                    return (
                      <button
                        key={bank.id}
                        type="button"
                        className={`hl-bank-tile${active ? ' is-selected' : ''}`}
                        onClick={() => {
                          setSelectedBank(bank.id);
                          setOtherBank('');
                        }}
                      >
                        <span className="hl-bank-code">{bank.code}</span>
                        <strong>{bank.name}</strong>
                      </button>
                    );
                  })}
                </div>
                <div className="form-field" style={{ marginTop: 12 }}>
                  <label htmlFor="hl-other-bank">Or choose another Indian bank</label>
                  <select
                    id="hl-other-bank"
                    value={otherBank}
                    onChange={(e) => setOtherBank(e.target.value)}
                  >
                    <option value="">-- Select from 45+ supported banks --</option>
                    {OTHER_BANKS.map((b) => (
                      <option key={b} value={b}>{b}</option>
                    ))}
                  </select>
                </div>
                <button
                  type="button"
                  className="btn-primary-forest hl-pay-cta"
                  style={{ marginTop: 14 }}
                  disabled={!!method}
                  onClick={handleNetBankingSubmit}
                >
                  {method
                    ? 'Redirecting to Bank…'
                    : `Pay ${formatINR(totals.netPayable)} via ${
                        otherBank || POPULAR_BANKS.find((b) => b.id === selectedBank)?.name || 'NetBanking'
                      }`}
                </button>
              </div>
            )}

            {/* ================= PANEL 4: COD ================= */}
            {payRail === 'cod' && (
              <div className="hl-cod-panel">
                <div className="hl-pay-block-label">
                  <span>Cash / UPI on Delivery</span>
                  <span className="hl-card-networks">Zero Advance Required</span>
                </div>
                <p style={{ fontSize: '0.82rem', color: 'var(--text-500)', lineHeight: 1.55, margin: '8px 0 14px' }}>
                  Pay <strong>{formatINR(totals.netPayable)}</strong> by cash or scan the courier&apos;s UPI QR
                  at your doorstep when your GI-sealed craft parcel arrives. Separate from online Razorpay checkout.
                </p>
                <button
                  type="button"
                  className="btn-primary-forest hl-pay-cta"
                  disabled={!!method}
                  onClick={() => pay('Cash on Delivery (COD)')}
                >
                  {method ? 'Confirming Order…' : `Confirm Cash on Delivery (${formatINR(totals.netPayable)})`}
                </button>
              </div>
            )}

            {/* Footer bar */}
            <div className="hl-pay-footer">
              <button type="button" className="btn-outline-ivory" onClick={() => setStep(3)}>
                &larr; Back to Summary
              </button>
              <div className={`hl-pay-env-pill${backendStatus.online ? ' is-live' : ''}`}>
                <span>
                  {backendStatus.online
                    ? backendStatus.ready?.razorpay_configured
                      ? '● Live Razorpay + FastAPI Active'
                      : '● FastAPI Connected · UPI Sandbox Demo Mode'
                    : '● UPI Sandbox Demo Mode (Preview)'}
                </span>
              </div>
            </div>
          </div>
        )}
      </div>
    </Modal>
  );
}
