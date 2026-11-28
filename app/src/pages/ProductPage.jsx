import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useSearchParams, useNavigate, Link } from 'react-router-dom';
import { useStore, mapDbListingToProduct } from '../state/StoreContext.jsx';
import { useClerkBridge } from '../data/clerkConfig.js';
import {
  canAttemptBackend,
  createProductReview,
  fetchCatalogProductById,
  fetchProductReviews
} from '../services/apiClient.js';
import { formatINR, asset } from '../utils/legacy.js';
import { srcSetFor } from '../data/imageVariants.js';
import { artisanProfileHref, featuredPortraitFor } from '../utils/artisans.js';
import { buildThumbnails, techniqueTag, techniqueSpec } from '../data/pdpThumbs.js';
import ProductGallery from '../components/ProductGallery.jsx';
import ProductCard from '../components/ProductCard.jsx';
import '../styles/pdp.css';
import { IconPackage, IconShield, IconTruck } from '../components/LineIcons.jsx';
import { describeCraft } from '../data/guilds.js';
import { fetchPassportByProduct, passportQrSvgUrl } from '../services/craftproofApi.js';

/* ==========================================================================
   ProductPage
   --------------------------------------------------------------------------
   Gallery on the left, the full record on the right, suggestions and the
   visitor's own trail underneath. Everything the static initPDP() wrote into
   the DOM one getElementById at a time is derived here from the product.

   The page deliberately keeps its own footer rather than the site footer: the
   PDP is a focused acquisition surface and the static build treated it that
   way.
   ========================================================================== */

const ShieldIcon = (props) => (
  <svg
    className="pdp-ico-shield"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="1.9"
    strokeLinecap="round"
    strokeLinejoin="round"
    aria-hidden="true"
    {...props}
  >
    <path d="M12 3l7 3v5.5c0 4.4-3 8-7 9.5-4-1.5-7-5.1-7-9.5V6l7-3z" />
    <path d="M9 12l2 2 4-4" />
  </svg>
);

export default function ProductPage() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const clerkAuth = useClerkBridge();
  const {
    catalogue,
    artisans: dbArtisans,
    dbSyncStatus,
    isRealSignedIn,
    buyerProfile,
    reviews: storeReviews,
    productById,
    pushRecent,
    recentlyViewedItems,
    wishlist,
    toggleWishlist,
    addToCart,
    addReview,
    openModal,
    openDrawer,
    clearRecentlyViewed,
    toast
  } = useStore();

  const rawId = (params.get('id') || '').trim();
  const cachedProduct = rawId ? productById(rawId) : catalogue[0] || null;
  const [fetchedProduct, setFetchedProduct] = useState(null);
  const [lookupLoading, setLookupLoading] = useState(Boolean(rawId && !cachedProduct));
  const [rejectedByDb, setRejectedByDb] = useState(false);

  useEffect(() => {
    let active = true;
    if (!rawId) {
      setFetchedProduct(null);
      setLookupLoading(false);
      setRejectedByDb(false);
      return () => {
        active = false;
      };
    }

    async function verifyListingInDb() {
      setLookupLoading(true);
      setRejectedByDb(false);
      try {
        const token = clerkAuth.isSignedIn && clerkAuth.getToken ? await clerkAuth.getToken() : null;
        const row = await fetchCatalogProductById(rawId, token);
        if (!active) return;
        const mapped = mapDbListingToProduct(row);
        setFetchedProduct(mapped);
        setLookupLoading(false);
        /* Canonicalise legacy code or slug URLs to the unique database UUID `?id=<uuid>` */
        if (mapped.id && rawId.toLowerCase() !== String(mapped.id).toLowerCase()) {
          navigate(`/product?id=${encodeURIComponent(mapped.id)}`, { replace: true });
        }
      } catch (err) {
        if (!active) return;
        setFetchedProduct(null);
        if (err?.status === 404 || err?.status === 422) {
          setRejectedByDb(true);
        }
        setLookupLoading(false);
      }
    }

    verifyListingInDb();
    return () => {
      active = false;
    };
  }, [rawId, clerkAuth.isSignedIn, clerkAuth.getToken, navigate]);

  const product = rejectedByDb ? null : fetchedProduct || cachedProduct;
  const [craftPassport, setCraftPassport] = useState(null);
  const [reviewsData, setReviewsData] = useState(null);
  const [reviewsLoading, setReviewsLoading] = useState(false);
  const [reviewFormOpen, setReviewFormOpen] = useState(false);
  const [reviewRating, setReviewRating] = useState(5);
  const [reviewTitle, setReviewTitle] = useState('');
  const [reviewCity, setReviewCity] = useState(buyerProfile?.city || '');
  const [reviewBody, setReviewBody] = useState('');
  const [reviewError, setReviewError] = useState('');
  const [submittingReview, setSubmittingReview] = useState(false);

  const loadProductReviews = useCallback(async () => {
    const ref = product?.listingId || product?.productId || product?.id;
    if (!ref || !canAttemptBackend()) {
      setReviewsData(null);
      return;
    }
    setReviewsLoading(true);
    try {
      const token = clerkAuth.isSignedIn && clerkAuth.getToken ? await clerkAuth.getToken() : null;
      const res = await fetchProductReviews(ref, token);
      setReviewsData(res);
    } catch {
      setReviewsData(null);
    } finally {
      setReviewsLoading(false);
    }
  }, [product?.listingId, product?.productId, product?.id, clerkAuth]);

  useEffect(() => {
    loadProductReviews();
  }, [loadProductReviews]);

  useEffect(() => {
    if (!reviewCity && buyerProfile?.city) {
      setReviewCity(buyerProfile.city);
    }
  }, [buyerProfile?.city, reviewCity]);

  useEffect(() => {
    let active = true;
    const ref = product?.listingId || product?.productId || product?.slug || product?.id;
    if (!ref) return undefined;
    fetchPassportByProduct(ref)
      .then((data) => {
        if (active) setCraftPassport(data);
      })
      .catch(() => {
        if (active) setCraftPassport(null);
      });
    return () => {
      active = false;
    };
  }, [product?.listingId, product?.productId, product?.slug, product?.id]);

  useEffect(() => {
    if (!rawId && product?.id) {
      navigate(`/product?id=${encodeURIComponent(product.id)}`, { replace: true });
    }
  }, [rawId, product?.id, navigate]);

  useEffect(() => {
    if (product) pushRecent(product.id);
  }, [product?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (product) document.title = `${product.title} — HunarLink Valley Craft Guild`;
    return () => {
      document.title = 'HunarLink — GI-Certified Kashmiri Handicrafts Marketplace';
    };
  }, [product?.title]); // eslint-disable-line react-hooks/exhaustive-deps

  const thumbs = useMemo(
    () => (product ? buildThumbnails(product, catalogue) : []),
    [product?.id, catalogue] // eslint-disable-line react-hooks/exhaustive-deps
  );

  const suggestions = useMemo(() => {
    if (!product) return [];
    return catalogue
      .filter((p) => p.id !== product.id && p.guild === product.guild)
      .slice(0, 4);
  }, [product?.id, product?.guild, catalogue]); // eslint-disable-line react-hooks/exhaustive-deps

  if ((lookupLoading || dbSyncStatus === 'loading') && !product) {
    return (
      <main id="main-content" className="container" style={{ padding: '80px 0', textAlign: 'center' }}>
        <p style={{ opacity: 0.75, fontSize: '0.96rem' }}>
          Loading heirloom craft record from HunarLink database&hellip;
        </p>
      </main>
    );
  }

  if (!product) {
    return (
      <main id="main-content" className="container" style={{ padding: '80px 0', textAlign: 'center' }}>
        <h1 style={{ fontFamily: 'var(--font-serif)', fontSize: '2rem', marginBottom: 12 }}>
          Craft not found
        </h1>
        <p style={{ opacity: 0.75, marginBottom: 20 }}>
          No active craft listing matches ID <code>{rawId || 'unknown'}</code> in the HunarLink database.
        </p>
        <button type="button" className="btn-primary-forest" onClick={() => navigate('/')}>
          Back to the Heritage Store
        </button>
      </main>
    );
  }

  const wished = wishlist.includes(product.id);
  const retailPrice = product.originalPrice ?? product.mrp;
  const discountPct = Math.round(((retailPrice - product.price) / retailPrice) * 100);

  const localStoreReviews = (storeReviews?.[product.id] || []).map((r, idx) => ({
    id: r.id || `local-${idx}`,
    author_name: r.author || 'Collector',
    author_city: r.city || 'India',
    rating: Number(r.stars || 5),
    title: r.title || null,
    review_body: r.text || '',
    is_verified_purchase: false,
    created_at: r.date || null,
    source: 'local'
  }));
  const displayedReviews = reviewsData?.reviews || localStoreReviews;
  const effectiveRating = Number(reviewsData?.average_rating ?? product.rating ?? 4.9);
  const effectiveReviewCount = Number(
    reviewsData?.total_reviews ?? Math.max(product.reviewCount || 0, displayedReviews.length)
  );
  const effectiveBreakdown = reviewsData?.rating_breakdown || [
    { stars: 5, count: effectiveReviewCount, percentage: effectiveReviewCount ? 88 : 0 },
    { stars: 4, count: 0, percentage: effectiveReviewCount ? 10 : 0 },
    { stars: 3, count: 0, percentage: effectiveReviewCount ? 2 : 0 },
    { stars: 2, count: 0, percentage: 0 },
    { stars: 1, count: 0, percentage: 0 }
  ];

  const ratingLabelFor = (stars) => {
    if (stars === 5) return 'Heirloom Masterpiece';
    if (stars === 4) return 'Very Good Craftsmanship';
    if (stars === 3) return 'Good';
    if (stars === 2) return 'Fair';
    return 'Needs Improvement';
  };

  async function handlePublishReview(e) {
    e.preventDefault();
    setReviewError('');
    if (!isRealSignedIn || !clerkAuth.isSignedIn) {
      navigate(`/login?redirect=${encodeURIComponent(`/product?id=${product.id}`)}`);
      return;
    }
    const bodyText = reviewBody.trim();
    if (bodyText.length < 5) {
      setReviewError('Please write at least 5 characters sharing your feedback on this craft.');
      return;
    }
    setSubmittingReview(true);
    try {
      if (canAttemptBackend() && clerkAuth.getToken) {
        const token = await clerkAuth.getToken();
        if (!token) {
          throw new Error('Your session expired. Please sign in again to submit a review.');
        }
        const ref = product.listingId || product.productId || product.id;
        await createProductReview(
          ref,
          {
            rating: reviewRating,
            title: reviewTitle.trim() || null,
            review_body: bodyText,
            author_city: reviewCity.trim() || null
          },
          token
        );
        await loadProductReviews();
      } else {
        addReview(product.id, {
          stars: reviewRating,
          title: reviewTitle.trim(),
          city: reviewCity.trim() || 'India',
          text: bodyText
        });
      }
      setReviewTitle('');
      setReviewBody('');
      setReviewRating(5);
      setReviewFormOpen(false);
      toast('Thank you — your review is now published.', 'success');
    } catch (err) {
      setReviewError(err?.message || 'Could not publish your review. Please try again.');
    } finally {
      setSubmittingReview(false);
    }
  }

  const buyNow = () => {
    addToCart(product.id, 1);
    if (isRealSignedIn) {
      openModal('checkout');
    }
  };

  return (
    <>
      <div className="pdp-breadcrumb-bar">
        <div className="container pdp-breadcrumb-inner">
          <div className="pdp-bc-left">
            <Link to="/" className="pdp-back-arrow" title="Back to Marketplace">
              &larr;
            </Link>
            <Link to="/">HOME</Link>
            <span className="pdp-bc-sep">/</span>
            <Link to="/#marketplace-section">EXPLORE CRAFTS</Link>
            <span className="pdp-bc-sep">/</span>
            {/* This crumb names a category, so it goes to that category's own
                page. It has been wrong twice: first a link to the marketplace
                that applied no filter at all, then one that applied a filter to
                the whole store and scrolled you into it. Both promised a
                category and delivered the catalogue. /category/:slug is the
                page the crumb was always describing. */}
            <Link
              to={`/category/${product.technique ? `${product.guild}-${product.technique}` : product.guild}`}
              className="pdp-bc-guild"
            >
              {product.guildLabel.toUpperCase()}
              {product.technique ? ` / ${product.technique.toUpperCase()}` : ''}
            </Link>
            <span className="pdp-bc-sep">/</span>
            <strong className="pdp-bc-current">{product.title.toUpperCase()}</strong>
          </div>
          <div className="pdp-bc-right" id="pdp-bc-cluster">
            <ShieldIcon />
            <span>{`Verified Mastercraft \u2022 ${product.district} Cluster`}</span>
          </div>
        </div>
      </div>

      <main className="pdp-showcase-container" id="main-content">
        <div className="pdp-showcase-grid">
          <ProductGallery
            product={product}
            thumbs={thumbs}
            wished={wished}
            onToggleWish={() => toggleWishlist(product.id)}
          />

          <div className="pdp-details-col">
            <div className="pdp-pills-row">
              <span className="pdp-badge-pill gi" id="pdp-tag-gi">
                <ShieldIcon /> GI-CERTIFIED
              </span>
              <span className="pdp-badge-pill carved" id="pdp-tag-technique">
                {techniqueTag(product.guild, product.technique)}
              </span>
              <span className="pdp-badge-pill valley" id="pdp-tag-cluster">
                {product.district.toUpperCase()} CLUSTER
              </span>
            </div>

            <h1 className="pdp-title" id="pdp-title">
              {product.title}
            </h1>
            <div className="pdp-subtitle" id="pdp-subtitle">
              {describeCraft(product.guild, product.technique)} &mdash; Heritage Kashmiri Masterpiece
            </div>

            <Link
              to={artisanProfileHref(product)}
              className="pdp-artisan-box pdp-artisan-box-link"
              aria-label={`Open ${product.artisan}'s full workshop profile`}
            >
              <div className="pdp-artisan-profile">
                {(() => {
                  const avatarImg =
                    featuredPortraitFor(product, dbArtisans) || product.image || 'assets/image_1.jpg';
                  const avatarSrcSet = srcSetFor(avatarImg);
                  return (
                    <picture>
                      {avatarSrcSet && (
                        <source type="image/webp" srcSet={avatarSrcSet} sizes="112px" />
                      )}
                      <img
                        loading="lazy"
                        decoding="async"
                        src={asset(avatarImg)}
                        alt={product.artisan}
                        className="pdp-artisan-avatar-img"
                        id="pdp-artisan-avatar"
                      />
                    </picture>
                  );
                })()}
                <div>
                  <div className="pdp-artisan-eyebrow">
                    <ShieldIcon /> VERIFIED MASTER ARTISAN
                  </div>
                  <div className="pdp-artisan-fullname" id="pdp-artisan-name">
                    {product.artisan}
                  </div>
                  <div className="pdp-artisan-location" id="pdp-artisan-location">
                    Traditional Atelier, {product.district} Cluster, Kashmir
                  </div>
                </div>
              </div>
              <div className="pdp-artisan-right">
                <div className="pdp-artisan-exp-pill" id="pdp-artisan-exp">
                  {product.loomHours > 500 ? '45+' : '30+'} Yrs Lineage
                </div>
                <span className="pdp-artisan-open">View profile &rarr;</span>
              </div>
            </Link>

            <div className="pdp-price-wrap">
              <div className="pdp-price-eyebrow">PATRON ACQUISITION PRICE</div>
              <div className="pdp-price-row">
                <span className="pdp-price-main" id="pdp-price-main">
                  {formatINR(product.price)}
                </span>
                <span className="pdp-price-mrp" id="pdp-price-mrp">
                  {formatINR(retailPrice)}
                </span>
                <span className="pdp-price-discount" id="pdp-price-discount">
                  Save {formatINR(retailPrice - product.price)} ({discountPct}% Off)
                </span>
              </div>
              <div className="pdp-price-note" id="pdp-price-note">
                Original market price {formatINR(retailPrice)} &middot; retail
                galleries typically list this piece higher because of two or
                three middlemen. Here the artisan is paid directly.
              </div>
            </div>

            <p className="pdp-narrative" id="pdp-narrative">
              {product.description}
            </p>

            <div className="pdp-specs-grid">
              <div className="pdp-spec-box">
                <div className="pdp-spec-label">TECHNIQUE</div>
                <div className="pdp-spec-val" id="pdp-spec-technique-val">
                  {techniqueSpec(product.guild, product.purityMetric, product.technique)}
                </div>
              </div>
              <div className="pdp-spec-box">
                <div className="pdp-spec-label">MATERIAL</div>
                <div className="pdp-spec-val" id="pdp-spec-material-val">
                  {product.purityMetric}
                </div>
              </div>
              <div className="pdp-spec-box">
                <div className="pdp-spec-label">ORIGIN</div>
                <div className="pdp-spec-val" id="pdp-spec-origin-val">
                  {product.district} Cluster, Jammu &amp; Kashmir
                </div>
              </div>
              <div className="pdp-spec-box">
                <div className="pdp-spec-label">CRAFTING TIME</div>
                <div className="pdp-spec-val" id="pdp-spec-hours-val">
                  {product.loomHours}+ Master Loom Hours
                </div>
              </div>
            </div>

            <div className="pdp-cta-row">
              <button type="button" className="btn-pdp-buy-now" id="btn-pdp-buy-now" onClick={buyNow}>
                <span><IconPackage size={15} /></span>BUY NOW
              </button>
              <button
                type="button"
                className="btn-pdp-add-cart"
                id="btn-pdp-add-cart"
                onClick={() => {
                  addToCart(product.id, 1);
                  openDrawer('cart');
                }}
              >
                <span>
                  <svg
                    className="pdp-ico-shield"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="1.9"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    aria-hidden="true"
                  >
                    <path d="M6 7h12l1.5 13.5a1 1 0 0 1-1 1.1H5.5a1 1 0 0 1-1-1.1L6 7z" />
                    <path d="M9 10V5.5a3 3 0 0 1 6 0V10" />
                  </svg>
                </span>{' '}
                ADD TO SHOPPING BAG
              </button>
            </div>

            <div className="pdp-trust-grid">
              <div className="pdp-trust-tile">
                <div className="pdp-trust-tile-icon">
                  <ShieldIcon />
                </div>
                <div className="pdp-trust-tile-title">Govt GI Tagged</div>
                <div className="pdp-trust-tile-desc">Digital QR Seal</div>
              </div>
              <div className="pdp-trust-tile">
                <div className="pdp-trust-tile-icon"><IconTruck size={15} /></div>
                <div className="pdp-trust-tile-title">Insured Transit</div>
                <div className="pdp-trust-tile-desc">India &amp; Overseas</div>
              </div>
              <div className="pdp-trust-tile">
                <div className="pdp-trust-tile-icon"><IconShield size={14} /></div>
                <div className="pdp-trust-tile-title">Sovereign Escrow</div>
                <div className="pdp-trust-tile-desc">Protected Payment</div>
              </div>
            </div>
          </div>
        </div>

        {/* CraftProof Digital Passport */}
        {craftPassport && (
          <section style={{ margin: '28px 0 12px' }}>
            <div className="cp-card" style={{ borderColor: 'rgba(20,56,42,0.22)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 16 }}>
                <div style={{ flex: 1, minWidth: 260 }}>
                  <div className="cp-kicker">CraftProof &middot; Living Digital Craft Passport</div>
                  <h2 style={{ margin: '0 0 6px', fontSize: '1.25rem', fontFamily: 'var(--font-serif, Georgia, serif)' }}>
                    Inspect Provenance, Evidence &amp; Fair-Craft Pricing
                  </h2>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'center', marginBottom: 8 }}>
                    <span className={`cp-badge cp-badge--${craftPassport.overall_trust_level}`}>
                      {craftPassport.overall_trust_level.replace(/_/g, ' ')}
                    </span>
                    <span style={{ fontSize: '0.8rem', color: '#4b5563' }}>
                      Code: <strong style={{ fontFamily: 'monospace' }}>{craftPassport.passport_code}</strong> &middot;{' '}
                      <strong>{craftPassport.summary_counts.verified_count}</strong> verified /{' '}
                      <strong>{craftPassport.summary_counts.total_claims}</strong> total claims
                    </span>
                  </div>
                  {craftPassport.fair_craft_breakdown?.fairness_summary && (
                    <p style={{ margin: '0 0 10px', fontSize: '0.83rem', color: '#374151' }}>
                      {craftPassport.fair_craft_breakdown.fairness_summary}
                    </p>
                  )}
                  <Link
                    to={`/passport/${craftPassport.passport_code}`}
                    className="cp-btn cp-btn-primary cp-btn-sm"
                  >
                    Open Full Craft Passport &amp; Timeline &rarr;
                  </Link>
                </div>
                <Link
                  to={`/passport/${craftPassport.passport_code}`}
                  className="cp-qr-box"
                  style={{ textDecoration: 'none' }}
                  aria-label="Open Craft Passport via QR"
                >
                  <img
                    src={passportQrSvgUrl(craftPassport.passport_code)}
                    alt={`QR Code for ${craftPassport.passport_code}`}
                    style={{ width: 96, height: 96 }}
                  />
                  <span style={{ fontSize: '0.68rem', fontWeight: 700, color: '#14382a', fontFamily: 'monospace' }}>
                    {craftPassport.passport_code}
                  </span>
                </Link>
              </div>
            </div>
          </section>
        )}

        {/* Collector Reviews & Write a Review */}
        <section className="pdp-reviews-section" id="pdp-reviews-section" aria-labelledby="pdp-reviews-heading">
          <div className="pdp-reviews-card">
            <div className="pdp-reviews-head">
              <div>
                <div className="pdp-section-kicker">COLLECTOR REVIEWS &amp; IMPRESSIONS</div>
                <h2 className="pdp-section-h2" id="pdp-reviews-heading">
                  Craft Ratings &amp; Previous Reviews
                </h2>
              </div>
              <button
                type="button"
                id="btn-pdp-write-review"
                className={`pdp-reviews-toggle-btn${reviewFormOpen ? ' is-open' : ''}`}
                onClick={() => {
                  setReviewError('');
                  setReviewFormOpen((prev) => !prev);
                }}
              >
                {reviewFormOpen ? 'Close Review Form' : 'Write a Review'}
              </button>
            </div>

            <div className="pdp-reviews-summary">
              <div className="pdp-reviews-score">
                <div className="pdp-reviews-score-num">{effectiveRating.toFixed(1)}</div>
                <div className="pdp-reviews-stars" aria-label={`${effectiveRating.toFixed(1)} out of 5 stars`}>
                  {Array.from({ length: 5 }).map((_, idx) => (
                    <span key={idx}>{idx < Math.round(effectiveRating) ? '★' : '☆'}</span>
                  ))}
                </div>
                <div className="pdp-reviews-count-note">
                  {effectiveReviewCount} verified {effectiveReviewCount === 1 ? 'rating' : 'ratings'}
                </div>
              </div>

              <div className="pdp-rating-bars">
                {effectiveBreakdown.map((row) => (
                  <div className="pdp-rating-bar-row" key={row.stars}>
                    <span>{row.stars} Stars</span>
                    <div className="pdp-rating-bar-track" aria-hidden="true">
                      <div className="pdp-rating-bar-fill" style={{ width: `${row.percentage}%` }} />
                    </div>
                    <span>{row.percentage}%</span>
                  </div>
                ))}
              </div>
            </div>

            {reviewFormOpen && (
              <form className="pdp-review-form" onSubmit={handlePublishReview}>
                {!isRealSignedIn || !clerkAuth.isSignedIn ? (
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
                    <span style={{ fontSize: '0.86rem', color: '#2E3D34', fontWeight: 600 }}>
                      Sign in with your HunarLink Collector account to publish a verified review for{' '}
                      <strong>{product.title}</strong>.
                    </span>
                    <Link
                      to={`/login?redirect=${encodeURIComponent(`/product?id=${product.id}`)}`}
                      className="pdp-reviews-toggle-btn"
                      style={{ textDecoration: 'none' }}
                    >
                      Sign In to Review &rarr;
                    </Link>
                  </div>
                ) : (
                  <>
                    <div className="pdp-review-field">
                      <label>Your Rating</label>
                      <div className="pdp-star-picker" role="radiogroup" aria-label="Select star rating">
                        {[1, 2, 3, 4, 5].map((starVal) => (
                          <button
                            key={starVal}
                            type="button"
                            className={`pdp-star-btn${reviewRating >= starVal ? ' is-active' : ''}`}
                            aria-label={`${starVal} star${starVal > 1 ? 's' : ''}`}
                            aria-pressed={reviewRating === starVal}
                            onClick={() => setReviewRating(starVal)}
                          >
                            ★
                          </button>
                        ))}
                        <span className="pdp-star-label">
                          {reviewRating} / 5 &mdash; {ratingLabelFor(reviewRating)}
                        </span>
                      </div>
                    </div>

                    <div className="pdp-review-form-grid">
                      <div className="pdp-review-field">
                        <label htmlFor="pdp-review-title-input">Review Headline (Optional)</label>
                        <input
                          id="pdp-review-title-input"
                          type="text"
                          className="pdp-review-input"
                          maxLength={160}
                          placeholder="e.g. Exquisite hand-knotted weave & richness"
                          value={reviewTitle}
                          onChange={(e) => setReviewTitle(e.target.value)}
                        />
                      </div>
                      <div className="pdp-review-field">
                        <label htmlFor="pdp-review-city-input">Your City (Optional)</label>
                        <input
                          id="pdp-review-city-input"
                          type="text"
                          className="pdp-review-input"
                          maxLength={100}
                          placeholder="e.g. New Delhi"
                          value={reviewCity}
                          onChange={(e) => setReviewCity(e.target.value)}
                        />
                      </div>
                    </div>

                    <div className="pdp-review-field">
                      <label htmlFor="pdp-review-body-input">Your Review *</label>
                      <textarea
                        id="pdp-review-body-input"
                        rows={3}
                        required
                        minLength={5}
                        maxLength={2000}
                        className="pdp-review-textarea"
                        placeholder={`Share your experience with ${product.artisan}'s ${product.title}...`}
                        value={reviewBody}
                        onChange={(e) => setReviewBody(e.target.value)}
                      />
                    </div>

                    {reviewError && <div className="pdp-review-error">{reviewError}</div>}

                    <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10 }}>
                      <button
                        type="button"
                        className="pdp-clear-recent-btn"
                        onClick={() => setReviewFormOpen(false)}
                      >
                        Cancel
                      </button>
                      <button
                        type="submit"
                        className="pdp-reviews-toggle-btn"
                        disabled={submittingReview}
                      >
                        {submittingReview ? 'Publishing Review…' : 'Publish Review'}
                      </button>
                    </div>
                  </>
                )}
              </form>
            )}

            {reviewsLoading && displayedReviews.length === 0 ? (
              <p style={{ margin: 0, fontSize: '0.85rem', color: '#5D7065' }}>
                Loading collector reviews&hellip;
              </p>
            ) : displayedReviews.length === 0 ? (
              <div className="pdp-review-item" style={{ maxWidth: '100%' }}>
                <p className="pdp-review-body" style={{ color: '#5D7065' }}>
                  This craft holds an average rating of <strong>{effectiveRating.toFixed(1)} ★</strong>{' '}
                  across {effectiveReviewCount} collector acquisitions. Be the first to write a detailed
                  review above!
                </p>
              </div>
            ) : (
              <div className="pdp-review-list" id="pdp-review-list">
                {displayedReviews.map((rev) => (
                  <article className="pdp-review-item" key={rev.id}>
                    <div className="pdp-review-item-top">
                      <div>
                        <div className="pdp-review-author">{rev.author_name}</div>
                        <div className="pdp-review-meta">
                          {rev.author_city || 'India'}
                          {rev.created_at
                            ? ` • ${new Date(rev.created_at).toLocaleDateString('en-IN', {
                                day: 'numeric',
                                month: 'short',
                                year: 'numeric'
                              })}`
                            : ''}
                        </div>
                      </div>
                      <span
                        className={`pdp-review-badge ${
                          rev.source === 'heritage_archive'
                            ? 'is-archive'
                            : rev.is_verified_purchase
                            ? 'is-verified'
                            : 'is-collector'
                        }`}
                      >
                        {rev.source === 'heritage_archive'
                          ? 'Heritage Archive'
                          : rev.is_verified_purchase
                          ? 'Verified Purchase'
                          : 'Collector Review'}
                      </span>
                    </div>

                    <div className="pdp-reviews-stars" aria-label={`${rev.rating} out of 5 stars`}>
                      {Array.from({ length: 5 }).map((_, idx) => (
                        <span key={idx}>{idx < rev.rating ? '★' : '☆'}</span>
                      ))}
                    </div>

                    {rev.title && <h3 className="pdp-review-title">{rev.title}</h3>}
                    <p className="pdp-review-body">{rev.review_body}</p>

                    {rev.seller_reply && (
                      <div className="pdp-seller-reply">
                        <strong>Artisan Workshop Reply:</strong> {rev.seller_reply}
                      </div>
                    )}
                  </article>
                ))}
              </div>
            )}
          </div>
        </section>

        <section className="pdp-suggestions-section" id="pdp-suggestions-section">
          <div className="pdp-section-header-split">
            <div>
              <div className="pdp-section-kicker">CURATED GUILD SUGGESTIONS</div>
              <h2 className="pdp-section-h2">Similar Valley Masterpieces</h2>
            </div>
            <span style={{ fontSize: '0.82rem', color: '#64756A' }}>
              Explore matching authentic Kashmiri craftsmanship
            </span>
          </div>
          <div className="product-grid" id="pdp-suggestions-grid">
            {suggestions.map((p) => (
              <ProductCard key={`sug-${p.id}`} product={p} />
            ))}
          </div>
        </section>

        {recentlyViewedItems.length > 1 && (
          <section className="pdp-recent-section" id="pdp-recent-section">
            <div className="pdp-section-header-split">
              <div>
                <div className="pdp-section-kicker">YOUR DISCOVERY TRAIL</div>
                <h2 className="pdp-section-h2">Recently Viewed Heirlooms</h2>
              </div>
              <button type="button" className="pdp-clear-recent-btn" onClick={clearRecentlyViewed}>
                Clear History
              </button>
            </div>
            <div className="product-grid" id="pdp-recent-grid">
              {recentlyViewedItems
                .filter((p) => p.id !== product.id)
                .map((p) => (
                  <ProductCard key={`rec-${p.id}`} product={p} />
                ))}
            </div>
          </section>
        )}
      </main>
    </>
  );
}
