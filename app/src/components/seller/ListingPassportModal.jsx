import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { uploadGuardrailDocument } from '../../services/apiClient.js';
import {
  attachSellerClaimEvidence,
  createOrGetSellerPassport,
  passportQrSvgUrl
} from '../../services/craftproofApi.js';

export default function ListingPassportModal({ listing, clerk, onClose, toast }) {
  const [passport, setPassport] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [uploadingClaimId, setUploadingClaimId] = useState('');
  const [evidenceType, setEvidenceType] = useState('WORKSHOP_PHOTO');
  const [caption, setCaption] = useState('');

  useEffect(() => {
    let active = true;
    async function initPassport() {
      setLoading(true);
      setError('');
      try {
        const token = clerk ? await clerk.getToken() : null;
        if (!token) throw new Error('Sign in as artisan to manage Craft Passport.');
        const data = await createOrGetSellerPassport(listing.listing_id, {}, token);
        if (active) setPassport(data);
      } catch (err) {
        if (active) setError(err?.message || 'Could not load Craft Passport for this listing.');
      } finally {
        if (active) setLoading(false);
      }
    }
    if (listing?.listing_id) initPassport();
    return () => { active = false; };
  }, [listing, clerk]);

  async function handleAttachFile(claimId, file) {
    if (!file || uploadingClaimId) return;
    setUploadingClaimId(claimId);
    setError('');
    try {
      const token = await clerk.getToken();
      const uploaded = await uploadGuardrailDocument(file, 'claim_evidence', token);
      const res = await attachSellerClaimEvidence(
        claimId,
        {
          evidence_type: evidenceType,
          file_scan_id: uploaded.scan_id,
          caption: caption.trim() || `Supporting ${evidenceType.replace(/_/g, ' ').toLowerCase()} uploaded by artisan`
        },
        token
      );
      setPassport(res.passport);
      setCaption('');
      if (toast) toast('Evidence uploaded (SHA-256 verified) & sent to Admin verification queue!', 'success');
    } catch (err) {
      setError(err?.message || 'Evidence upload failed.');
    } finally {
      setUploadingClaimId('');
    }
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 1200,
        background: 'rgba(15, 23, 20, 0.58)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 16
      }}
      onClick={onClose}
    >
      <div
        className="cp-card"
        style={{ width: '100%', maxWidth: 740, maxHeight: '88vh', overflowY: 'auto' }}
        onClick={(e) => e.stopPropagation()}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 10, marginBottom: 12 }}>
          <div>
            <div className="cp-kicker">CraftProof &middot; Manage Passport &amp; Evidence</div>
            <h3 style={{ margin: 0, fontFamily: 'var(--font-serif, Georgia, serif)' }}>{listing?.title}</h3>
          </div>
          <button type="button" className="cp-btn cp-btn-outline cp-btn-sm" onClick={onClose}>
            Close
          </button>
        </div>

        {loading && <p>Loading Craft Passport…</p>}
        {error && <div style={{ color: '#b91c1c', fontSize: '0.84rem', marginBottom: 10 }}>{error}</div>}

        {passport && (
          <>
            <div style={{ display: 'flex', gap: 16, alignItems: 'center', flexWrap: 'wrap', padding: 14, borderRadius: 12, background: '#f5f2eb', marginBottom: 14 }}>
              <div className="cp-qr-box" style={{ padding: 6 }}>
                <img src={passportQrSvgUrl(passport.passport_code)} alt="Passport QR" style={{ width: 96, height: 96 }} />
              </div>
              <div style={{ flex: 1, minWidth: 220 }}>
                <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap', marginBottom: 6 }}>
                  <strong style={{ fontFamily: 'monospace' }}>{passport.passport_code}</strong>
                  <span className={`cp-badge cp-badge--${passport.overall_trust_level}`}>
                    {passport.overall_trust_level.replace(/_/g, ' ')}
                  </span>
                </div>
                <p style={{ margin: '0 0 8px', fontSize: '0.8rem', color: '#4b5563' }}>
                  Attach workshop photos, GI certificates, or lab reports to move any claim from{' '}
                  <strong>SELLER DECLARED</strong> to <strong>EVIDENCE SUBMITTED</strong> for Human Admin verification.
                </p>
                <Link to={`/passport/${passport.passport_code}`} target="_blank" rel="noreferrer" className="cp-btn cp-btn-primary cp-btn-sm">
                  Open Public QR Passport ↗
                </Link>
              </div>
            </div>

            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 12 }}>
              <select
                value={evidenceType}
                onChange={(e) => setEvidenceType(e.target.value)}
                style={{ padding: '7px 10px', borderRadius: 8, border: '1px solid #d1d5db', fontSize: '0.82rem' }}
              >
                <option value="WORKSHOP_PHOTO">Workshop / Loom Photo</option>
                <option value="GI_CERTIFICATE">GI Certificate</option>
                <option value="LAB_REPORT">Fiber / Lab Purity Report</option>
                <option value="ARTISAN_CARD">Artisan ID Card</option>
                <option value="INVOICE_RAW_MATERIAL">Raw Material Invoice</option>
              </select>
              <input
                type="text"
                value={caption}
                onChange={(e) => setCaption(e.target.value)}
                placeholder="Optional caption for reviewer..."
                style={{ flex: 1, minWidth: 200, padding: '7px 10px', borderRadius: 8, border: '1px solid #d1d5db', fontSize: '0.82rem' }}
              />
            </div>

            {(passport.all_claims || []).map((cl) => (
              <div key={cl.claim_id} className="cp-claim-item">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8 }}>
                  <div>
                    <strong style={{ fontSize: '0.88rem' }}>{cl.claim_title}:</strong>{' '}
                    <span style={{ fontSize: '0.85rem' }}>{cl.claim_value}</span>
                  </div>
                  <span className={`cp-badge cp-badge--${cl.verification_status}`}>
                    {cl.verification_status.replace(/_/g, ' ')}
                  </span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8, marginTop: 8 }}>
                  <span style={{ fontSize: '0.75rem', color: '#6b7280' }}>
                    Attached evidence files: <strong>{cl.evidence?.length || 0}</strong>
                  </span>
                  <label className="cp-btn cp-btn-outline cp-btn-sm" style={{ margin: 0 }}>
                    {uploadingClaimId === cl.claim_id ? 'Uploading & Hashing…' : 'Upload Proof (PDF/JPG/PNG)'}
                    <input
                      type="file"
                      accept=".pdf,.jpg,.jpeg,.png,.webp"
                      style={{ display: 'none' }}
                      disabled={Boolean(uploadingClaimId)}
                      onChange={(e) => {
                        const f = e.target.files?.[0];
                        if (f) handleAttachFile(cl.claim_id, f);
                        e.target.value = '';
                      }}
                    />
                  </label>
                </div>
              </div>
            ))}
          </>
        )}
      </div>
    </div>
  );
}
