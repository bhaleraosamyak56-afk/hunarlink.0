import React, { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  decideAdminCraftClaim,
  fetchAdminCraftClaims
} from '../../services/craftproofApi.js';

const STATUS_FILTERS = [
  { id: '', label: 'All Claims' },
  { id: 'EVIDENCE_SUBMITTED', label: 'Evidence Submitted' },
  { id: 'SELLER_DECLARED', label: 'Seller Declared' },
  { id: 'UNDER_REVIEW', label: 'Under Review' },
  { id: 'HUMAN_VERIFIED', label: 'Human Verified' },
  { id: 'THIRD_PARTY_VERIFIED', label: 'Third-Party Verified' },
  { id: 'REJECTED', label: 'Rejected' }
];

export default function AdminCraftProofTab({ adminToken, toast }) {
  const [filter, setFilter] = useState('');
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState('');
  const [notesByClaim, setNotesByClaim] = useState({});
  const [authorityByClaim, setAuthorityByClaim] = useState({});

  const load = useCallback(async () => {
    if (!adminToken) return;
    setLoading(true);
    try {
      const res = await fetchAdminCraftClaims(adminToken, filter);
      setItems(res.items || []);
    } catch (err) {
      if (toast) toast(err?.message || 'Could not load CraftProof claims.', 'error');
    } finally {
      setLoading(false);
    }
  }, [adminToken, filter, toast]);

  useEffect(() => {
    load();
  }, [load]);

  async function submitDecision(claimId, decisionStatus) {
    const notes = (notesByClaim[claimId] || '').trim() || `Admin reviewed evidence and marked claim ${decisionStatus}.`;
    const authority = (authorityByClaim[claimId] || '').trim() || 'HunarLink Human Verification Desk';
    setBusyId(claimId);
    try {
      await decideAdminCraftClaim(
        claimId,
        {
          decision_status: decisionStatus,
          decision_notes: notes,
          verified_by_authority: authority
        },
        adminToken
      );
      if (toast) toast(`Claim updated to ${decisionStatus.replace(/_/g, ' ')} — live Passport refreshed!`, 'success');
      await load();
    } catch (err) {
      if (toast) toast(err?.message || 'Could not apply verification decision.', 'error');
    } finally {
      setBusyId('');
    }
  }

  return (
    <div className="section-card">
      <div className="section-card-head" style={{ flexWrap: 'wrap', gap: 10 }}>
        <div>
          <h3 className="section-card-title">CraftProof &mdash; Human Claim Verification Desk</h3>
          <p style={{ fontSize: '0.82rem', color: 'var(--text-500)', margin: '2px 0 0' }}>
            Only Human Administrators here can promote a product claim to{' '}
            <strong>HUMAN_VERIFIED</strong> or <strong>THIRD_PARTY_VERIFIED</strong> on the public QR Craft Passport.
          </p>
        </div>
        <button type="button" className="cp-btn cp-btn-outline cp-btn-sm" onClick={load} disabled={loading}>
          Refresh Queue
        </button>
      </div>

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 14 }}>
        {STATUS_FILTERS.map((f) => (
          <button
            key={f.id || 'all'}
            type="button"
            className={`cp-btn cp-btn-sm ${filter === f.id ? 'cp-btn-primary' : 'cp-btn-outline'}`}
            onClick={() => setFilter(f.id)}
          >
            {f.label}
          </button>
        ))}
      </div>

      {loading ? (
        <p style={{ fontSize: '0.88rem', opacity: 0.7 }}>Loading CraftProof claims…</p>
      ) : items.length === 0 ? (
        <p style={{ fontSize: '0.88rem', opacity: 0.75 }}>No craft claims match this filter.</p>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {items.map((cl) => (
            <div key={cl.claim_id} className="cp-claim-item" style={{ background: '#fffdf8' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 8 }}>
                <div>
                  <div style={{ fontSize: '0.76rem', color: '#6b7280' }}>
                    <strong>{cl.product_name}</strong> &middot; {cl.artisan_store_name} ({cl.artisan_district || 'J&K'}) &middot;{' '}
                    <Link to={`/passport/${cl.passport_code}`} target="_blank" rel="noreferrer" style={{ color: '#14382a', fontWeight: 700 }}>
                      Open QR Passport ({cl.passport_code}) ↗
                    </Link>
                  </div>
                  <div style={{ fontWeight: 700, fontSize: '0.94rem', marginTop: 3 }}>
                    [{cl.claim_type}] {cl.claim_title}: <span style={{ fontWeight: 500 }}>{cl.claim_value}</span>
                  </div>
                </div>
                <span className={`cp-badge cp-badge--${cl.verification_status}`}>
                  {cl.verification_status.replace(/_/g, ' ')}
                </span>
              </div>

              {cl.evidence?.length > 0 ? (
                <div style={{ marginTop: 8, padding: '8px 10px', borderRadius: 8, background: '#eff6ff', fontSize: '0.78rem', color: '#1e3a8a' }}>
                  <strong>Attached Evidence ({cl.evidence.length}):</strong>
                  {cl.evidence.map((ev) => (
                    <div key={ev.evidence_id}>
                      &bull; {ev.evidence_type}: {ev.original_filename || ev.external_reference_url || ev.caption}
                      {ev.sha256_hash && <span style={{ fontFamily: 'monospace' }}> (SHA-256: {ev.sha256_hash.slice(0, 14)}…)</span>}
                    </div>
                  ))}
                </div>
              ) : (
                <div style={{ marginTop: 6, fontSize: '0.76rem', color: '#92400e' }}>
                  No supporting evidence file uploaded yet for this claim.
                </div>
              )}

              <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 8, marginTop: 10 }}>
                <input
                  type="text"
                  placeholder="Mandatory human review notes (recorded on public timeline)..."
                  value={notesByClaim[cl.claim_id] ?? cl.decision_notes ?? ''}
                  onChange={(e) => setNotesByClaim({ ...notesByClaim, [cl.claim_id]: e.target.value })}
                  style={{ padding: '7px 10px', borderRadius: 8, border: '1px solid #d1d5db', fontSize: '0.82rem' }}
                />
                <input
                  type="text"
                  placeholder="Authority (e.g. CDI / HunarLink Desk)"
                  value={authorityByClaim[cl.claim_id] ?? cl.verified_by_authority ?? 'HunarLink Human Verification Desk'}
                  onChange={(e) => setAuthorityByClaim({ ...authorityByClaim, [cl.claim_id]: e.target.value })}
                  style={{ padding: '7px 10px', borderRadius: 8, border: '1px solid #d1d5db', fontSize: '0.82rem' }}
                />
              </div>

              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 10 }}>
                <button
                  type="button"
                  className="cp-btn cp-btn-primary cp-btn-sm"
                  disabled={busyId === cl.claim_id}
                  onClick={() => submitDecision(cl.claim_id, 'HUMAN_VERIFIED')}
                >
                  Approve (Human Verified)
                </button>
                <button
                  type="button"
                  className="cp-btn cp-btn-saffron cp-btn-sm"
                  disabled={busyId === cl.claim_id}
                  onClick={() => submitDecision(cl.claim_id, 'THIRD_PARTY_VERIFIED')}
                >
                  Third-Party Verified
                </button>
                <button
                  type="button"
                  className="cp-btn cp-btn-outline cp-btn-sm"
                  disabled={busyId === cl.claim_id}
                  onClick={() => submitDecision(cl.claim_id, 'NOT_ESTABLISHED')}
                >
                  Not Established
                </button>
                <button
                  type="button"
                  className="cp-btn cp-btn-danger cp-btn-sm"
                  disabled={busyId === cl.claim_id}
                  onClick={() => submitDecision(cl.claim_id, 'REJECTED')}
                >
                  Reject Claim
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
