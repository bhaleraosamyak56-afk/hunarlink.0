import React from 'react';
import { evaluatePassword } from '../utils/passwordPolicy.js';

export default function PasswordChecklist({ password = '', confirmPassword = null }) {
  const pwd = String(password || '');
  const evalRes = evaluatePassword(pwd);
  const progressPct = pwd.length === 0 ? 0 : Math.round((evalRes.passedCount / evalRes.totalRules) * 100);
  const hasConfirm = confirmPassword !== null;
  const confirmMatches = hasConfirm && pwd.length > 0 && pwd === String(confirmPassword || '');

  return (
    <div
      className="hl-pw-checklist"
      aria-live="polite"
      style={{
        marginTop: '0.45rem',
        padding: '0.65rem 0.78rem',
        borderRadius: '10px',
        background: '#f7f5ee',
        border: '1px solid rgba(20, 56, 42, 0.14)',
        fontSize: '0.76rem',
        lineHeight: 1.45
      }}
    >
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: '0.35rem',
          fontWeight: 700,
          color: '#14382a'
        }}
      >
        <span>Password Requirements</span>
        {pwd.length > 0 && (
          <span style={{ color: evalRes.strengthColor, fontSize: '0.73rem' }}>
            {evalRes.strengthLabel}
          </span>
        )}
      </div>

      <div
        style={{
          height: '4px',
          width: '100%',
          background: 'rgba(20, 56, 42, 0.1)',
          borderRadius: '999px',
          overflow: 'hidden',
          marginBottom: '0.5rem'
        }}
      >
        <div
          style={{
            height: '100%',
            width: `${progressPct}%`,
            background: evalRes.strengthColor,
            transition: 'width 180ms ease, background 180ms ease'
          }}
        />
      </div>

      <ul
        style={{
          listStyle: 'none',
          margin: 0,
          padding: 0,
          display: 'grid',
          gap: '0.24rem'
        }}
      >
        {evalRes.results.map((rule) => {
          const activeColor = rule.passed
            ? '#15803d'
            : pwd.length > 0
              ? '#64748b'
              : '#4b5b53';
          return (
            <li
              key={rule.id}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '0.42rem',
                color: activeColor,
                fontWeight: rule.passed ? 600 : 400
              }}
            >
              <span
                aria-hidden="true"
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  width: '14px',
                  height: '14px',
                  borderRadius: '50%',
                  fontSize: '0.66rem',
                  fontWeight: 800,
                  background: rule.passed ? '#dcfce7' : 'rgba(20, 56, 42, 0.08)',
                  color: rule.passed ? '#15803d' : '#64748b',
                  flexShrink: 0
                }}
              >
                {rule.passed ? '✓' : '•'}
              </span>
              <span>{rule.label}</span>
            </li>
          );
        })}

        {hasConfirm && String(confirmPassword || '').length > 0 && (
          <li
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.42rem',
              color: confirmMatches ? '#15803d' : '#b91c1c',
              fontWeight: 600,
              marginTop: '0.15rem'
            }}
          >
            <span
              aria-hidden="true"
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                width: '14px',
                height: '14px',
                borderRadius: '50%',
                fontSize: '0.66rem',
                fontWeight: 800,
                background: confirmMatches ? '#dcfce7' : '#fee2e2',
                color: confirmMatches ? '#15803d' : '#b91c1c',
                flexShrink: 0
              }}
            >
              {confirmMatches ? '✓' : '✕'}
            </span>
            <span>{confirmMatches ? 'Passwords match' : 'Passwords do not match'}</span>
          </li>
        )}
      </ul>
    </div>
  );
}
