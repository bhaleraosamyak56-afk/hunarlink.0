import React, { useState } from 'react';
import { useClerkBridge } from '../../data/clerkConfig.js';
import {
  dispatchDemandInquiries,
  matchDemandBridge,
  parseDemandBrief
} from '../../services/craftproofApi.js';

const SAMPLE_BRIEFS = [
  {
    label: 'Cluster Demo: 85 Walnut Boxes (Auto Multi-Artisan Pool)',
    text: 'Need 85 hand-carved Kashmiri walnut jewelry boxes for a Delhi hotel conference within 25 days, budget ₹2,000–₹2,800 per unit, prefer GI verified artisans.'
  },
  {
    label: 'Boutique Demo: 18 Sozni Pashmina Shawls',
    text: 'Looking for 18 hand-embroidered Sozni Pashmina shawls for our Mumbai boutique launch in 30 days, budget ₹12,000 to ₹18,000 per piece, GI verified preferred.'
  }
];

const inr = (n) => '₹' + Number(n || 0).toLocaleString('en-IN');

export default function DemandBridgePanel({ defaultBuyerName = '', defaultBuyerEmail = '', toast }) {
  const { getToken, isSignedIn } = useClerkBridge();
  const [rawBrief, setRawBrief] = useState(SAMPLE_BRIEFS[0].text);
  const [parsed, setParsed] = useState(null);
  const [buyerName, setBuyerName] = useState(defaultBuyerName || '');
  const [buyerEmail, setBuyerEmail] = useState(defaultBuyerEmail || '');
  const [parseLoading, setParseLoading] = useState(false);
  const [matchLoading, setMatchLoading] = useState(false);
  const [dispatching, setDispatching] = useState(false);
  const [matchResult, setMatchResult] = useState(null);
  const [dispatchedInfo, setDispatchedInfo] = useState(null);
  const [error, setError] = useState('');

  async function handleParse() {
    if (rawBrief.trim().length < 10 || parseLoading) return;
    setParseLoading(true);
    setError('');
    setDispatchedInfo(null);
    try {
      const res = await parseDemandBrief(rawBrief.trim());
      setParsed(res.structured_requirements);
    } catch (err) {
      setError(err?.message || 'Could not parse buyer brief.');
    } finally {
      setParseLoading(false);
    }
  }

  async function handleMatch() {
    if (matchLoading) return;
    setMatchLoading(true);
    setError('');
    setDispatchedInfo(null);
    try {
      let reqStruct = parsed;
      if (!reqStruct) {
        const pRes = await parseDemandBrief(rawBrief.trim());
        reqStruct = pRes.structured_requirements;
        setParsed(reqStruct);
      }
      const token = isSignedIn && getToken ? await getToken() : null;
      const res = await matchDemandBridge(
        {
          raw_request_text: rawBrief.trim(),
          buyer_name: buyerName.trim() || 'Bulk Sourcing Buyer',
          buyer_email: buyerEmail.trim() || null,
          category_slug: reqStruct.category_slug || null,
          craft_technique: reqStruct.craft_technique || null,
          requested_quantity: Number(reqStruct.requested_quantity || 25),
          budget_min_inr: reqStruct.budget_min_inr ? Number(reqStruct.budget_min_inr) : null,
          budget_max_inr: reqStruct.budget_max_inr ? Number(reqStruct.budget_max_inr) : null,
          target_delivery_days: reqStruct.target_delivery_days ? Number(reqStruct.target_delivery_days) : 30,
          preferred_district: reqStruct.preferred_district || null,
          requires_verified_claims: Boolean(reqStruct.requires_verified_claims),
          allow_cluster_pooling: reqStruct.allow_cluster_pooling !== false,
          customization_notes: reqStruct.customization_notes || null
        },
        token
      );
      setMatchResult(res);
    } catch (err) {
      setError(err?.message || 'Could not match artisans.');
    } finally {
      setMatchLoading(false);
    }
  }

  async function handleDispatchCluster() {
    if (!matchResult?.demand_request_id || dispatching) return;
    setDispatching(true);
    setError('');
    try {
      const token = isSignedIn && getToken ? await getToken() : null;
      const res = await dispatchDemandInquiries(
        matchResult.demand_request_id,
        {
          buyer_name: buyerName.trim() || 'Bulk Sourcing Buyer',
          buyer_email: buyerEmail.trim() || null
        },
        token
      );
      setDispatchedInfo(res);
      if (toast) {
        toast(`Dispatched brief ${res.request_code} directly to ${res.contacted_count} verified artisan workshop(s)!`, 'success');
      }
    } catch (err) {
      setError(err?.message || 'Could not dispatch cluster inquiries.');
    } finally {
      setDispatching(false);
    }
  }

  return (
    <section className="cp-shell" style={{ paddingTop: 18, paddingBottom: 14 }}>
      <div className="cp-card-emerald" style={{ marginBottom: 16 }}>
        <div className="cp-kicker">Pillar 4 &middot; Demand Bridge + Multi-Artisan Cluster Fulfillment</div>
        <h2 style={{ margin: '0 0 8px', fontSize: '1.65rem', fontFamily: 'var(--font-serif, Georgia, serif)', color: '#fffdf8' }}>
          Source Bulk Heritage Crafts Directly &mdash; Auto-Pooling Small Rural Workshops
        </h2>
        <p style={{ margin: 0, fontSize: '0.88rem', opacity: 0.92, maxWidth: 820, lineHeight: 1.55 }}>
          Describe your corporate, hotel, or boutique order in plain English. HunarLink extracts structured specs, and
          our <strong>100% deterministic MySQL matching engine</strong> evaluates all real Kashmiri workshops — automatically
          forming a <strong>Multi-Artisan Fulfillment Cluster</strong> when volume exceeds any single atelier&apos;s capacity.
        </p>
      </div>

      <div className="cp-card">
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 10 }}>
          {SAMPLE_BRIEFS.map((b) => (
            <button
              key={b.label}
              type="button"
              className="cp-btn cp-btn-outline cp-btn-sm"
              onClick={() => {
                setRawBrief(b.text);
                setParsed(null);
                setMatchResult(null);
              }}
            >
              {b.label}
            </button>
          ))}
        </div>

        <textarea
          rows={3}
          value={rawBrief}
          onChange={(e) => setRawBrief(e.target.value)}
          placeholder="Describe quantity, craft, target budget per unit, delivery timeline, and GI verification preference..."
          style={{
            width: '100%',
            boxSizing: 'border-box',
            padding: '11px 13px',
            borderRadius: 10,
            border: '1px solid rgba(20,56,42,0.22)',
            fontSize: '0.88rem',
            fontFamily: 'inherit'
          }}
        />

        <div className="cp-grid-2" style={{ marginTop: 10 }}>
          <input
            type="text"
            value={buyerName}
            onChange={(e) => setBuyerName(e.target.value)}
            placeholder="Your Company / Buyer Name (e.g. Taj Hospitality)"
            style={{ padding: '9px 11px', borderRadius: 9, border: '1px solid #d1d5db', fontSize: '0.85rem' }}
          />
          <input
            type="email"
            value={buyerEmail}
            onChange={(e) => setBuyerEmail(e.target.value)}
            placeholder="Contact Email for Artisan Quotes"
            style={{ padding: '9px 11px', borderRadius: 9, border: '1px solid #d1d5db', fontSize: '0.85rem' }}
          />
        </div>

        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 12 }}>
          <button
            type="button"
            className="cp-btn cp-btn-outline"
            disabled={parseLoading || rawBrief.trim().length < 10}
            onClick={handleParse}
          >
            {parseLoading ? 'Extracting Brief…' : '1. Extract Structured Brief'}
          </button>
          <button
            type="button"
            className="cp-btn cp-btn-primary"
            disabled={matchLoading || rawBrief.trim().length < 10}
            onClick={handleMatch}
          >
            {matchLoading ? 'Scoring 53+ Artisans…' : '2. Match Artisans & Form Cluster →'}
          </button>
        </div>

        {error && (
          <div style={{ marginTop: 10, color: '#b91c1c', fontSize: '0.84rem' }}>{error}</div>
        )}

        {/* Editable Structured Brief */}
        {parsed && (
          <div style={{ marginTop: 14, padding: 14, borderRadius: 12, background: '#faf8f3', border: '1px solid rgba(20,56,42,0.14)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8, marginBottom: 10 }}>
              <strong style={{ fontSize: '0.86rem', color: '#14382a' }}>Structured Requirements (Editable Before Matching)</strong>
            </div>
            <div className="cp-grid-3">
              <label style={{ fontSize: '0.76rem', color: '#4b5563' }}>
                Craft Category
                <select
                  value={parsed.category_slug || 'walnut-wood'}
                  onChange={(e) => setParsed({ ...parsed, category_slug: e.target.value })}
                  style={{ display: 'block', width: '100%', marginTop: 4, padding: '7px 8px', borderRadius: 8, border: '1px solid #d1d5db' }}
                >
                  <option value="walnut-wood">Walnut Wood Carving</option>
                  <option value="pashmina">Pashmina &amp; Shawls</option>
                  <option value="kani-shawls">Kani Shawls</option>
                  <option value="kashmiri-carpets">Kashmiri Carpets</option>
                  <option value="papier-mache">Papier-Mâché</option>
                  <option value="copperware">Kashmiri Copperware</option>
                  <option value="saffron-pampore">Pampore Saffron</option>
                  <option value="crewel-embroidery">Crewel &amp; Embroidery</option>
                </select>
              </label>
              <label style={{ fontSize: '0.76rem', color: '#4b5563' }}>
                Order Quantity (Units)
                <input
                  type="number"
                  min={1}
                  value={parsed.requested_quantity || 25}
                  onChange={(e) => setParsed({ ...parsed, requested_quantity: Number(e.target.value) })}
                  style={{ display: 'block', width: '100%', boxSizing: 'border-box', marginTop: 4, padding: '7px 8px', borderRadius: 8, border: '1px solid #d1d5db' }}
                />
              </label>
              <label style={{ fontSize: '0.76rem', color: '#4b5563' }}>
                Target Delivery (Days)
                <input
                  type="number"
                  min={3}
                  value={parsed.target_delivery_days || 30}
                  onChange={(e) => setParsed({ ...parsed, target_delivery_days: Number(e.target.value) })}
                  style={{ display: 'block', width: '100%', boxSizing: 'border-box', marginTop: 4, padding: '7px 8px', borderRadius: 8, border: '1px solid #d1d5db' }}
                />
              </label>
              <label style={{ fontSize: '0.76rem', color: '#4b5563' }}>
                Budget Min (INR/unit)
                <input
                  type="number"
                  value={parsed.budget_min_inr ?? ''}
                  onChange={(e) => setParsed({ ...parsed, budget_min_inr: e.target.value ? Number(e.target.value) : null })}
                  style={{ display: 'block', width: '100%', boxSizing: 'border-box', marginTop: 4, padding: '7px 8px', borderRadius: 8, border: '1px solid #d1d5db' }}
                />
              </label>
              <label style={{ fontSize: '0.76rem', color: '#4b5563' }}>
                Budget Max (INR/unit)
                <input
                  type="number"
                  value={parsed.budget_max_inr ?? ''}
                  onChange={(e) => setParsed({ ...parsed, budget_max_inr: e.target.value ? Number(e.target.value) : null })}
                  style={{ display: 'block', width: '100%', boxSizing: 'border-box', marginTop: 4, padding: '7px 8px', borderRadius: 8, border: '1px solid #d1d5db' }}
                />
              </label>
              <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: '0.8rem', paddingTop: 18 }}>
                <input
                  type="checkbox"
                  checked={parsed.allow_cluster_pooling !== false}
                  onChange={(e) => setParsed({ ...parsed, allow_cluster_pooling: e.target.checked })}
                />
                Enable Multi-Artisan Cluster Pooling
              </label>
            </div>
          </div>
        )}

        {/* Deterministic Matching & Cluster Pooling Result */}
        {matchResult && (
          <div style={{ marginTop: 18 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 10, marginBottom: 12 }}>
              <div>
                <span className="cp-badge cp-badge--HUMAN_VERIFIED" style={{ marginRight: 8 }}>
                  Mode: {matchResult.fulfillment_mode.replace(/_/g, ' ')}
                </span>
                <span style={{ fontSize: '0.8rem', color: '#4b5563' }}>
                  Brief <strong>{matchResult.request_code}</strong> &middot; Evaluated{' '}
                  <strong>{matchResult.total_artisans_evaluated}</strong> active workshops deterministically
                </span>
              </div>
              {matchResult.matches?.length > 0 && (
                <button
                  type="button"
                  className="cp-btn cp-btn-saffron cp-btn-sm"
                  disabled={dispatching || Boolean(dispatchedInfo)}
                  onClick={handleDispatchCluster}
                >
                  {dispatchedInfo
                    ? `Dispatched to ${dispatchedInfo.contacted_count} Workshop(s) ✓`
                    : dispatching
                      ? 'Sending Brief…'
                      : matchResult.cluster_plan
                        ? `Dispatch Brief to Entire ${matchResult.cluster_plan.cluster_size}-Workshop Cluster`
                        : 'Send Direct Inquiry to Top Matched Artisan'}
                </button>
              )}
            </div>

            {/* Multi-Artisan Cluster Banner */}
            {matchResult.cluster_plan && (
              <div style={{ padding: 16, borderRadius: 14, background: '#ecfdf5', border: '2px solid #15803d', marginBottom: 14 }}>
                <div className="cp-kicker" style={{ color: '#15803d' }}>
                  Verified Multi-Artisan Fulfillment Cluster Formed Automatically
                </div>
                <p style={{ margin: '0 0 10px', fontSize: '0.86rem', color: '#064e3b' }}>
                  {matchResult.cluster_plan.why_cluster_formed}
                </p>
                <div className="cp-grid-3">
                  <div style={{ background: '#ffffff', padding: 10, borderRadius: 10 }}>
                    <div style={{ fontSize: '0.72rem', color: '#6b7280' }}>Cluster Coverage</div>
                    <div style={{ fontSize: '1.15rem', fontWeight: 700, color: '#15803d' }}>
                      {matchResult.cluster_plan.total_allocated_quantity} / {matchResult.cluster_plan.requested_quantity} units ({matchResult.cluster_plan.coverage_pct}%)
                    </div>
                  </div>
                  <div style={{ background: '#ffffff', padding: 10, borderRadius: 10 }}>
                    <div style={{ fontSize: '0.72rem', color: '#6b7280' }}>Blended Direct Unit Price</div>
                    <div style={{ fontSize: '1.15rem', fontWeight: 700, color: '#14382a' }}>
                      {inr(matchResult.cluster_plan.blended_unit_price_inr)} / unit
                    </div>
                  </div>
                  <div style={{ background: '#ffffff', padding: 10, borderRadius: 10 }}>
                    <div style={{ fontSize: '0.72rem', color: '#6b7280' }}>Parallel Cluster Delivery</div>
                    <div style={{ fontSize: '1.15rem', fontWeight: 700, color: '#b45309' }}>
                      ~{matchResult.cluster_plan.parallel_lead_time_days} days ({matchResult.cluster_plan.cluster_size} ateliers)
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Ranked Artisan Match Cards with Transparent Deterministic Math */}
            <div className="cp-grid-2">
              {(matchResult.matches || []).map((m) => (
                <div
                  key={m.match_id}
                  className={`cp-claim-item ${m.is_cluster_member ? 'cp-claim-item--verified' : ''}`}
                  style={{ marginBottom: 0 }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8 }}>
                    <div>
                      <div style={{ fontWeight: 700, fontSize: '0.95rem', color: '#14382a' }}>
                        #{m.match_rank} {m.store_name}
                      </div>
                      <div style={{ fontSize: '0.77rem', color: '#6b7280' }}>
                        {m.workshop_district || 'Jammu & Kashmir'} &middot; {m.craft_specialty}
                      </div>
                    </div>
                    <div style={{ textAlign: 'right' }}>
                      <div style={{ fontWeight: 800, fontSize: '1.05rem', color: '#14382a' }}>
                        {m.match_score}/100
                      </div>
                      {m.is_cluster_member && (
                        <span className="cp-badge cp-badge--HUMAN_VERIFIED">
                          Allocated: {m.allocated_quantity} units
                        </span>
                      )}
                    </div>
                  </div>

                  <div className="cp-score-bar-track" style={{ margin: '8px 0' }}>
                    <div className="cp-score-bar-fill" style={{ width: `${Math.min(100, m.match_score)}%` }} />
                  </div>

                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, fontSize: '0.77rem', color: '#374151', marginBottom: 6 }}>
                    <span>Capacity: <strong>{m.monthly_capacity_units}/mo</strong></span>
                    <span>Est: <strong>{inr(m.estimated_unit_price_inr)}/unit</strong></span>
                    <span>Lead: <strong>{m.estimated_lead_days} days</strong></span>
                    <span>Path: <strong>{m.verification_path}</strong></span>
                  </div>

                  <ul style={{ margin: 0, paddingLeft: 16, fontSize: '0.76rem', color: '#4b5563', lineHeight: 1.45 }}>
                    {(m.match_reasons || []).slice(0, 4).map((r, idx) => <li key={idx}>{r}</li>)}
                  </ul>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
