import React, { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import {
  fetchPassportByCode,
  passportQrSvgUrl
} from '../services/craftproofApi.js';

const formatStatus = (s) => String(s || 'SELLER_DECLARED').replace(/_/g, ' ');
const inr = (n) => '₹' + Number(n || 0).toLocaleString('en-IN');

export default function PassportPage() {
  const { code } = useParams();
  const [passport, setPassport] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  async function loadPassport() {
    setLoading(true);
    setError('');
    try {
      const data = await fetchPassportByCode(code);
      setPassport(data);
    } catch (err) {
      setError(err?.message || 'Craft Passport could not be loaded.');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadPassport();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [code]);

  if (loading) {
    return (
      <main id="main-content" className="cp-shell">
        <div className="cp-card" style={{ textAlign: 'center', padding: 48 }}>
          <div className="cp-kicker">CraftProof Trust Network</div>
          <p style={{ margin: 0 }}>Loading Digital Craft Passport <strong>{code}</strong>…</p>
        </div>
      </main>
    );
  }

  if (error || !passport) {
    return (
      <main id="main-content" className="cp-shell">
        <div className="cp-card" style={{ textAlign: 'center', padding: 42 }}>
          <div className="cp-kicker">CraftProof Passport Lookup</div>
          <h1 style={{ fontFamily: 'var(--font-serif, Georgia, serif)', marginTop: 4 }}>
            Passport Not Found
          </h1>
          <p style={{ color: '#4b5563' }}>{error || `No Craft Passport exists for code ${code}.`}</p>
          <Link to="/" className="cp-btn cp-btn-primary">Return to Marketplace</Link>
        </div>
      </main>
    );
  }

  const { product, artisan, verified_claims, unverified_claims, fair_craft_breakdown, verification_timeline } = passport;

  return (
    <main id="main-content" className="cp-shell">
      {/* Top Hero Banner with Live QR Code */}
      <section className="cp-card-emerald" style={{ marginBottom: 20 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 20 }}>
          <div style={{ flex: 1, minWidth: 260 }}>
            <div className="cp-kicker">HunarLink CraftProof &middot; Living Digital Craft Passport</div>
            <h1 style={{ margin: '0 0 8px', fontSize: '1.85rem', fontFamily: 'var(--font-serif, Georgia, serif)', color: '#fffdf8' }}>
              {product.name}
            </h1>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'center', marginBottom: 12 }}>
              <span className={`cp-badge cp-badge--${passport.overall_trust_level}`}>
                Status: {formatStatus(passport.overall_trust_level)}
              </span>
              <span style={{ fontSize: '0.82rem', opacity: 0.9 }}>
                Passport ID: <strong style={{ fontFamily: 'monospace' }}>{passport.passport_code}</strong>
              </span>
              <span style={{ fontSize: '0.82rem', opacity: 0.9 }}>
                &middot; {passport.summary_counts.verified_count} Verified / {passport.summary_counts.total_claims} Claims
              </span>
            </div>
            <p style={{ margin: '0 0 14px', fontSize: '0.88rem', opacity: 0.92, lineHeight: 1.55, maxWidth: 680 }}>
              Workshop: <strong>{artisan.store_name}</strong> ({artisan.workshop_district || product.origin_location}) &middot;{' '}
              Craft: <strong>{product.manufacturing_process}</strong> &middot; Direct Price:{' '}
              <strong>{product.selling_price_inr ? inr(product.selling_price_inr) : 'Contact Artisan'}</strong>
            </p>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10 }}>
              {product.product_id && (
                <Link to={`/product?id=${encodeURIComponent(product.product_id)}`} className="cp-btn cp-btn-saffron cp-btn-sm">
                  View Product Page &rarr;
                </Link>
              )}
              <button type="button" className="cp-btn cp-btn-sm" style={{ background: 'rgba(255,255,255,0.14)', color: '#fffdf8' }} onClick={loadPassport}>
                Refresh Live Status
              </button>
            </div>
          </div>

          <div className="cp-qr-box">
            <img
              src={passportQrSvgUrl(passport.passport_code)}
              alt={`QR Code for Craft Passport ${passport.passport_code}`}
            />
            <span style={{ fontSize: '0.7rem', fontWeight: 700, color: '#14382a', fontFamily: 'monospace' }}>
              {passport.passport_code}
            </span>
            <span style={{ fontSize: '0.67rem', color: '#4b5563' }}>Scan to verify live</span>
          </div>
        </div>
      </section>

      {/* Hard Trust Disclosure Banner */}
      <div className="cp-disclaimer-banner" style={{ marginBottom: 18 }}>
        <strong>Zero-Hallucination Trust Boundary:</strong> {passport.trust_disclosure}
      </div>

      {/* Explicit Two-Column Provenance Split: Independently Verified vs Seller Declared */}
      <section className="cp-grid-2" style={{ marginBottom: 18 }}>
        <div className="cp-card">
          <div className="cp-kicker" style={{ color: '#15803d' }}>Independently Verified Facts ({verified_claims.length})</div>
          <h2 style={{ margin: '0 0 12px', fontSize: '1.15rem', fontFamily: 'var(--font-serif, Georgia, serif)' }}>
            Human &amp; Third-Party Verified Claims
          </h2>
          {verified_claims.length === 0 ? (
            <div style={{ padding: '16px 14px', borderRadius: 12, background: '#f9fafb', border: '1px dashed #d1d5db', fontSize: '0.85rem', color: '#4b5563' }}>
              <strong>No claims have been independently verified yet.</strong> All statements for this craft are currently
              Artisan Declarations awaiting evidence review by a human HunarLink verifier.
            </div>
          ) : (
            verified_claims.map((cl) => (
              <div key={cl.claim_id} className="cp-claim-item cp-claim-item--verified">
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, flexWrap: 'wrap', marginBottom: 4 }}>
                  <strong style={{ fontSize: '0.9rem' }}>{cl.claim_title}</strong>
                  <span className={`cp-badge cp-badge--${cl.verification_status}`}>
                    {formatStatus(cl.verification_status)}
                  </span>
                </div>
                <div style={{ fontSize: '0.88rem', color: '#1f2937', marginBottom: 6 }}>{cl.claim_value}</div>
                {cl.verified_by_authority && (
                  <div style={{ fontSize: '0.76rem', color: '#166534' }}>
                    Verified by: <strong>{cl.verified_by_authority}</strong>
                    {cl.verified_at ? ` on ${new Date(cl.verified_at).toLocaleDateString('en-IN')}` : ''}
                  </div>
                )}
                {cl.decision_notes && (
                  <div style={{ fontSize: '0.76rem', color: '#374151', marginTop: 4 }}>
                    Reviewer note: {cl.decision_notes}
                  </div>
                )}
                {cl.evidence?.length > 0 && (
                  <div style={{ marginTop: 8, paddingTop: 6, borderTop: '1px solid rgba(21,128,61,0.16)', fontSize: '0.74rem' }}>
                    {cl.evidence.map((ev) => (
                      <div key={ev.evidence_id} style={{ color: '#14532d' }}>
                        Proof: <strong>{ev.evidence_type}</strong> {ev.original_filename || ev.caption || ''}
                        {ev.sha256_hash && <span style={{ fontFamily: 'monospace' }}> (SHA-256: {ev.sha256_hash.slice(0, 12)}…)</span>}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))
          )}
        </div>

        <div className="cp-card">
          <div className="cp-kicker">Artisan Declarations &amp; Pending Review ({unverified_claims.length})</div>
          <h2 style={{ margin: '0 0 12px', fontSize: '1.15rem', fontFamily: 'var(--font-serif, Georgia, serif)' }}>
            Unverified / Seller-Declared Claims
          </h2>
          {unverified_claims.length === 0 ? (
            <div style={{ padding: '16px 14px', borderRadius: 12, background: '#ecfdf5', fontSize: '0.85rem', color: '#065f46' }}>
              All recorded claims on this Craft Passport have been independently verified.
            </div>
          ) : (
            unverified_claims.map((cl) => (
              <div
                key={cl.claim_id}
                className={`cp-claim-item ${cl.verification_status === 'REJECTED' ? 'cp-claim-item--rejected' : 'cp-claim-item--unverified'}`}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, flexWrap: 'wrap', marginBottom: 4 }}>
                  <strong style={{ fontSize: '0.9rem' }}>{cl.claim_title}</strong>
                  <span className={`cp-badge cp-badge--${cl.verification_status}`}>
                    {formatStatus(cl.verification_status)}
                  </span>
                </div>
                <div style={{ fontSize: '0.88rem', color: '#1f2937', marginBottom: 4 }}>{cl.claim_value}</div>
                <div style={{ fontSize: '0.75rem', color: '#6b7280' }}>
                  Source: {formatStatus(cl.claim_source)} &middot; Supporting files attached: <strong>{cl.evidence?.length || 0}</strong>
                </div>
                {cl.decision_notes && (
                  <div style={{ fontSize: '0.76rem', color: '#991b1b', marginTop: 4 }}>
                    Note: {cl.decision_notes}
                  </div>
                )}
                {cl.evidence?.length > 0 && (
                  <div style={{ marginTop: 6, fontSize: '0.74rem', color: '#1e3a8a' }}>
                    {cl.evidence.map((ev) => (
                      <div key={ev.evidence_id}>
                        Submitted: <strong>{ev.evidence_type}</strong> {ev.original_filename || ev.caption || ''}
                        {ev.sha256_hash && <span style={{ fontFamily: 'monospace' }}> (SHA-256: {ev.sha256_hash.slice(0, 12)}…)</span>}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      </section>

      {/* Fair-Craft Value Breakdown + Physical Inspection Guide */}
      {fair_craft_breakdown && (
        <section className="cp-grid-2" style={{ marginBottom: 18 }}>
          <div className="cp-card">
            <div className="cp-kicker">Why Genuine Handmade Costs This</div>
            <h2 style={{ margin: '0 0 10px', fontSize: '1.12rem', fontFamily: 'var(--font-serif, Georgia, serif)' }}>
              Fair-Craft Value Breakdown
            </h2>
            <p style={{ fontSize: '0.85rem', color: '#374151', marginTop: 0 }}>
              {fair_craft_breakdown.fairness_summary}
            </p>
            <div className="cp-grid-3" style={{ marginTop: 12 }}>
              <div style={{ background: '#f5f2eb', borderRadius: 10, padding: 10 }}>
                <div style={{ fontSize: '0.72rem', color: '#6b7280' }}>Est. Work-Days</div>
                <div style={{ fontSize: '1.15rem', fontWeight: 700, color: '#14382a' }}>
                  {fair_craft_breakdown.estimated_craft_days} days
                </div>
              </div>
              <div style={{ background: '#f5f2eb', borderRadius: 10, padding: 10 }}>
                <div style={{ fontSize: '0.72rem', color: '#6b7280' }}>Direct to Artisan</div>
                <div style={{ fontSize: '1.15rem', fontWeight: 700, color: '#15803d' }}>
                  {fair_craft_breakdown.direct_to_artisan_pct}%
                </div>
              </div>
              <div style={{ background: '#f5f2eb', borderRadius: 10, padding: 10 }}>
                <div style={{ fontSize: '0.72rem', color: '#6b7280' }}>Middleman Cut Saved</div>
                <div style={{ fontSize: '1.15rem', fontWeight: 700, color: '#b45309' }}>
                  {inr(fair_craft_breakdown.middleman_markup_avoided_inr)}
                </div>
              </div>
            </div>
          </div>

          <div className="cp-card">
            <div className="cp-kicker">Buyer Protection At Delivery</div>
            <h2 style={{ margin: '0 0 10px', fontSize: '1.12rem', fontFamily: 'var(--font-serif, Georgia, serif)' }}>
              Physical Authenticity Inspection Guide
            </h2>
            <ul style={{ margin: 0, paddingLeft: 18, fontSize: '0.85rem', color: '#374151', lineHeight: 1.6 }}>
              {(fair_craft_breakdown.physical_inspection_guide || []).map((tip, idx) => (
                <li key={idx} style={{ marginBottom: 6 }}>{tip}</li>
              ))}
            </ul>
          </div>
        </section>
      )}

      {/* Immutable Verification Audit Timeline */}
      <section className="cp-card" style={{ marginTop: 18 }}>
        <div className="cp-kicker">Immutable Audit Ledger</div>
        <h2 style={{ margin: '0 0 14px', fontSize: '1.12rem', fontFamily: 'var(--font-serif, Georgia, serif)' }}>
          Verification &amp; Provenance Timeline ({verification_timeline.length})
        </h2>
        {verification_timeline.map((ev) => (
          <div
            key={ev.event_id}
            className={`cp-timeline-item ${
              ['HUMAN_VERIFIED', 'THIRD_PARTY_VERIFIED'].includes(ev.to_status)
                ? 'cp-timeline-item--verified'
                : ''
            }`}
          >
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'center', marginBottom: 3 }}>
              <strong style={{ fontSize: '0.84rem' }}>{ev.event_type.replace(/_/g, ' ')}</strong>
              <span className="cp-badge cp-badge--NOT_ESTABLISHED" style={{ fontSize: '0.66rem' }}>
                Actor: {ev.actor_type}
              </span>
              {ev.to_status && (
                <span className={`cp-badge cp-badge--${ev.to_status}`} style={{ fontSize: '0.66rem' }}>
                  {formatStatus(ev.to_status)}
                </span>
              )}
              <span style={{ fontSize: '0.74rem', color: '#6b7280' }}>
                {ev.created_at ? new Date(ev.created_at).toLocaleString('en-IN') : ''}
              </span>
            </div>
            <div style={{ fontSize: '0.84rem', color: '#374151' }}>{ev.summary}</div>
          </div>
        ))}
      </section>
    </main>
  );
}
