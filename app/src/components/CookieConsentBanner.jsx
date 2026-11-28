import React, { useState } from 'react';
import { Link } from 'react-router-dom';

const CONSENT_KEY = 'hl_cookie_consent_v1';

function readSavedChoice() {
  try {
    const raw = window.localStorage.getItem(CONSENT_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export default function CookieConsentBanner() {
  const [choice, setChoice] = useState(() => readSavedChoice());

  if (choice) return null;

  const save = (analyticsAccepted) => {
    const record = {
      essential: true,
      analytics: Boolean(analyticsAccepted),
      decidedAt: new Date().toISOString()
    };
    try {
      window.localStorage.setItem(CONSENT_KEY, JSON.stringify(record));
    } catch {
      /* storage unavailable — non-fatal */
    }
    setChoice(record);
  };

  return (
    <aside
      role="dialog"
      aria-label="Cookie and Privacy Notice"
      style={{
        position: 'fixed',
        left: '16px',
        bottom: '16px',
        zIndex: 950,
        maxWidth: '460px',
        background: '#10281e',
        color: '#f7f5ee',
        border: '1px solid rgba(184, 133, 40, 0.45)',
        borderRadius: '14px',
        padding: '14px 16px',
        boxShadow: '0 14px 36px rgba(0, 0, 0, 0.28)',
        fontSize: '0.8rem',
        lineHeight: 1.5
      }}
    >
      <div style={{ fontWeight: 700, marginBottom: '4px', color: '#f3d285' }}>
        HunarLink Privacy &amp; Essential Cookies
      </div>
      <p style={{ margin: '0 0 10px', opacity: 0.92 }}>
        We use strictly essential cookies and browser storage for sign-in sessions and your cart.
        Optional craft-analytics remain off unless you accept. Read our{' '}
        <Link to="/privacy" style={{ color: '#f3d285', textDecoration: 'underline', fontWeight: 600 }}>
          DPDP Privacy Promise
        </Link>
        .
      </p>
      <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
        <button
          type="button"
          onClick={() => save(false)}
          style={{
            padding: '7px 12px',
            borderRadius: '999px',
            border: '1px solid rgba(255,255,255,0.35)',
            background: 'transparent',
            color: '#ffffff',
            fontSize: '0.76rem',
            fontWeight: 600,
            cursor: 'pointer'
          }}
        >
          Essential Only
        </button>
        <button
          type="button"
          onClick={() => save(true)}
          style={{
            padding: '7px 14px',
            borderRadius: '999px',
            border: 'none',
            background: '#d97724',
            color: '#ffffff',
            fontSize: '0.76rem',
            fontWeight: 700,
            cursor: 'pointer'
          }}
        >
          Accept Essential + Analytics
        </button>
      </div>
    </aside>
  );
}
