import React, { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { useStore, mapDbListingToProduct } from '../state/StoreContext.jsx';
import { useClerkBridge } from '../data/clerkConfig.js';
import { fetchArtisanById, fetchArtisanBySlug } from '../services/apiClient.js';
import {
  artisanProfileHref,
  collectArtisans,
  findArtisan,
  findSimilarArtisans,
  productProfileHref
} from '../utils/artisans.js';
import { srcSetFor } from '../data/imageVariants.js';
import { asset, formatINR } from '../utils/legacy.js';
import ProductCard from '../components/ProductCard.jsx';
import { ShieldCheck, Star } from '../components/Icons.jsx';
import {
  IconBadgeCheck,
  IconChat,
  IconMapPin,
  IconRupeeCoin,
  IconShield,
  IconSpark,
  IconTruck
} from '../components/LineIcons.jsx';
import '../styles/artisan-profile.css';

/* ==========================================================================
   ArtisanProfilePage — Dedicated DB-Backed Artisan Profile (`/artisan?id=<uuid>`)
   --------------------------------------------------------------------------
   Opens for any of the 53+ verified database artisans by unique UUID
   (`/artisan?id=<seller_profile_id>`, with backward-compatible `/artisans/:slug`
   normalising to `?id=<uuid>`). Validates directly against FastAPI
   (`GET /api/v1/artisans/detail?id=<uuid>`) so unverified or non-existent
   records return 404.
   ========================================================================== */

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export default function ArtisanProfilePage() {
  const { slug: routeSlug } = useParams();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const clerkAuth = useClerkBridge();

  const queryId = searchParams.get('id');
  const identifier = (queryId || routeSlug || '').trim();

  const {
    catalogue,
    artisans: dbArtisans,
    reviews: storeReviews,
    user,
    buyerProfile,
    isRealSignedIn,
    addToCart,
    openModal,
    addInquiry,
    addReview,
    toast
  } = useStore();

  const [fetchedDetail, setFetchedDetail] = useState(null);
  const [loading, setLoading] = useState(Boolean(identifier));
  const [rejectedByDb, setRejectedByDb] = useState(false);

  useEffect(() => {
    let active = true;
    if (!identifier) {
      setLoading(false);
      setRejectedByDb(true);
      return () => {
        active = false;
      };
    }

    async function verifyWithDb() {
      setLoading(true);
      setRejectedByDb(false);
      try {
        const token = clerkAuth.isSignedIn && clerkAuth.getToken ? await clerkAuth.getToken() : null;
        const res = UUID_RE.test(identifier)
          ? await fetchArtisanById(identifier, token)
          : await fetchArtisanBySlug(identifier, token);
        if (!active) return;
        setFetchedDetail(res);
        setLoading(false);

        /* Canonicalise legacy `/artisans/:slug` URLs to `/artisan?id=<uuid>` */
        if (!queryId && res?.seller_profile_id) {
          navigate(`/artisan?id=${encodeURIComponent(res.seller_profile_id)}`, { replace: true });
        }
      } catch (err) {
        if (!active) return;
        setFetchedDetail(null);
        if (err?.status === 404 || err?.status === 422) {
          setRejectedByDb(true);
        }
        setLoading(false);
      }
    }

    verifyWithDb();
    return () => {
      active = false;
    };
  }, [identifier, queryId, clerkAuth.isSignedIn, clerkAuth.getToken, navigate]);

  const mergedCatalogue = useMemo(() => {
    if (!fetchedDetail?.listings?.length) return catalogue;
    const existingIds = new Set(catalogue.map((p) => p.id));
    const extras = fetchedDetail.listings
      .map(mapDbListingToProduct)
      .filter((p) => !existingIds.has(p.id));
    return extras.length ? [...catalogue, ...extras] : catalogue;
  }, [catalogue, fetchedDetail]);

  const mergedDbArtisans = useMemo(() => {
    if (!fetchedDetail?.seller_profile_id) return dbArtisans;
    const exists = (dbArtisans || []).some(
      (a) => a.seller_profile_id === fetchedDetail.seller_profile_id
    );
    return exists ? dbArtisans : [...(dbArtisans || []), fetchedDetail];
  }, [dbArtisans, fetchedDetail]);

  const allArtisans = useMemo(
    () => collectArtisans(mergedCatalogue, storeReviews, mergedDbArtisans),
    [mergedCatalogue, storeReviews, mergedDbArtisans]
  );

  const artisan = useMemo(() => {
    if (rejectedByDb) return null;
    const target = fetchedDetail?.seller_profile_id || identifier;
    return findArtisan(allArtisans, target);
  }, [allArtisans, fetchedDetail, identifier, rejectedByDb]);

  useEffect(() => {
    if (artisan?.name) {
      document.title = `${artisan.name} — Verified Workshop · HunarLink`;
    }
  }, [artisan?.name]);

  const similarArtisans = useMemo(
    () => findSimilarArtisans(allArtisans, artisan, 3),
    [allArtisans, artisan]
  );

  const [techFilter, setTechFilter] = useState('all');
  const [sortBy, setSortBy] = useState('featured');

  const [contactOpen, setContactOpen] = useState(false);
  const [contactForm, setContactForm] = useState(() => ({
    name: user?.fullName || buyerProfile?.fullName || '',
    contact: user?.email || buyerProfile?.email || user?.phone || '',
    piece: 'custom',
    message: ''
  }));
  const [contactSent, setContactSent] = useState(false);

  const [reviewOpen, setReviewOpen] = useState(false);
  const [reviewDraft, setReviewDraft] = useState(() => ({
    author: user?.fullName || buyerProfile?.fullName || '',
    city: '',
    stars: 5,
    productId: '',
    text: ''
  }));

  useEffect(() => {
    setTechFilter('all');
    setSortBy('featured');
    setContactOpen(false);
    setContactSent(false);
    setReviewOpen(false);
    setContactForm((f) => ({ ...f, piece: 'custom', message: '' }));
  }, [identifier]);

  const visibleListings = useMemo(() => {
    if (!artisan) return [];
    let list = artisan.listings;
    if (techFilter !== 'all') {
      list = list.filter(
        (p) => String(p.technique || '').toLowerCase() === techFilter.toLowerCase()
      );
    }
    const copy = [...list];
    if (sortBy === 'price-asc') copy.sort((a, b) => (a.price || 0) - (b.price || 0));
    else if (sortBy === 'price-desc') copy.sort((a, b) => (b.price || 0) - (a.price || 0));
    else if (sortBy === 'rating') copy.sort((a, b) => (b.rating || 0) - (a.rating || 0));
    return copy;
  }, [artisan, techFilter, sortBy]);

  const techniqueTabs = useMemo(() => {
    if (!artisan) return [];
    const counts = new Map();
    for (const p of artisan.listings) {
      const t = String(p.technique || '').trim().toLowerCase();
      if (!t) continue;
      counts.set(t, (counts.get(t) || 0) + 1);
    }
    return [...counts.entries()];
  }, [artisan]);

  const ratingBreakdown = useMemo(() => {
    if (!artisan) return [];
    const base = artisan.avgRating || 4.9;
    const total = Math.max(artisan.totalReviews, 1);
    const fivePct = Math.min(96, Math.max(72, Math.round((base - 3.9) * 88)));
    const fourPct = Math.max(3, Math.round((100 - fivePct) * 0.78));
    const threePct = Math.max(0, 100 - fivePct - fourPct);
    return [
      { stars: 5, pct: fivePct, count: Math.round((total * fivePct) / 100) },
      { stars: 4, pct: fourPct, count: Math.round((total * fourPct) / 100) },
      { stars: 3, pct: threePct, count: Math.max(0, total - Math.round((total * (fivePct + fourPct)) / 100)) },
      { stars: 2, pct: 0, count: 0 },
      { stars: 1, pct: 0, count: 0 }
    ];
  }, [artisan]);

  if (loading && !artisan) {
    return (
      <main className="ap-page" id="main-content">
        <div className="container ap-wrap" style={{ paddingBlock: '5rem', textAlign: 'center' }}>
          <p className="ap-kicker">VERIFIED ARTISAN REGISTRY</p>
          <p style={{ opacity: 0.76, marginTop: '0.5rem' }}>
            Loading artisan workshop from HunarLink database&hellip;
          </p>
        </div>
      </main>
    );
  }

  if (!artisan || rejectedByDb) {
    return (
      <main className="ap-page" id="main-content">
        <div className="container ap-wrap">
          <div className="ap-not-found">
            <p className="ap-kicker">ARTISAN PROFILE</p>
            <h1>Artisan profile not found</h1>
            <p>
              No verified artisan workshop matches ID <code>{identifier || 'unknown'}</code> in the
              HunarLink database. Browse all verified masters in the directory instead.
            </p>
            <div className="ap-not-found-actions">
              <Link className="ap-btn ap-btn-primary" to="/artisans">
                Browse All Artisans
              </Link>
              <Link className="ap-btn ap-btn-outline" to="/">
                Back to Storefront
              </Link>
            </div>
          </div>
        </div>
      </main>
    );
  }

  const avatarSrcSet = srcSetFor(artisan.image);

  function handleBuyNow(productId) {
    addToCart(productId, 1);
    if (isRealSignedIn) {
      openModal('checkout');
    }
  }

  function handleShare() {
    const url = window.location.href;
    if (navigator.clipboard?.writeText) {
      navigator.clipboard.writeText(url).then(
        () => toast(`Profile link for ${artisan.name} copied!`, 'success'),
        () => toast('Copy the link from your browser address bar.')
      );
    } else {
      toast('Copy the link from your browser address bar.');
    }
  }

  function submitContact(e) {
    e.preventDefault();
    const sender = contactForm.name.trim();
    const replyTo = contactForm.contact.trim();
    const msg = contactForm.message.trim();
    if (!sender || !replyTo || !msg) {
      toast('Please fill in your name, email/phone, and message.');
      return;
    }

    const picked = artisan.listings.find((p) => p.id === contactForm.piece);
    const now = new Date();
    addInquiry({
      id: 'inq-prof-' + Date.now(),
      type:
        contactForm.piece === 'custom'
          ? `Bespoke Commission Inquiry (\u2192 ${artisan.name})`
          : `Direct Artisan Message (\u2192 ${artisan.name})`,
      author: `${sender} (${replyTo})`,
      productTitle: picked ? picked.title : `Custom ${artisan.craft} Commission`,
      date: now.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }),
      rating: 5,
      comment: msg,
      reply: ''
    });

    if (isRealSignedIn) {
      setContactSent(true);
      setContactForm((f) => ({ ...f, message: '' }));
      toast(`Message sent directly to ${artisan.name}'s workshop!`, 'success');
    }
  }

  function submitReview(e) {
    e.preventDefault();
    const author = reviewDraft.author.trim() || 'Verified Collector';
    const text = reviewDraft.text.trim();
    if (!text) {
      toast('Please write a short note about the craftsmanship.');
      return;
    }
    const targetProduct =
      artisan.listings.find((p) => p.id === reviewDraft.productId) || artisan.topProduct;
    if (!targetProduct) return;

    addReview(targetProduct.id, {
      id: 'rev-' + Date.now(),
      author,
      city: reviewDraft.city.trim() || 'India',
      rating: Number(reviewDraft.stars) || 5,
      comment: text,
      date: new Date().toLocaleDateString('en-IN', {
        day: '2-digit',
        month: 'short',
        year: 'numeric'
      })
    });

    if (isRealSignedIn) {
      setReviewDraft((d) => ({ ...d, text: '' }));
      setReviewOpen(false);
      toast(`Thank you! Review published for ${artisan.name}.`, 'success');
    }
  }

  return (
    <main className="ap-page" id="main-content" data-artisan-uuid={artisan.id}>
      {/* Top breadcrumb strip */}
      <div className="ap-crumb-bar">
        <div className="container ap-wrap ap-crumb-inner">
          <nav className="ap-breadcrumbs" aria-label="Breadcrumb">
            <Link to="/artisans" className="ap-back-link">
              <span aria-hidden="true">&larr;</span> All Artisans
            </Link>
            <span className="ap-crumb-sep" aria-hidden="true">/</span>
            <Link to={`/category/${artisan.primaryGuild}`}>
              {artisan.guilds[0]?.label || artisan.craft}
            </Link>
            <span className="ap-crumb-sep" aria-hidden="true">/</span>
            <span aria-current="page">{artisan.name}</span>
          </nav>

          <button type="button" className="ap-share-pill" onClick={handleShare}>
            Share Profile
          </button>
        </div>
      </div>

      {/* Main Fiverr-style 2-column profile body */}
      <div className="container ap-wrap ap-layout">
        {/* ======================== LEFT COLUMN ======================== */}
        <div className="ap-main">
          {/* 1. Identity Hero Card */}
          <section className="ap-card ap-hero-card" aria-labelledby="artisan-profile-name">
            <div className="ap-identity-row">
              <div className="ap-avatar-wrap">
                <picture>
                  {avatarSrcSet && (
                    <source type="image/webp" srcSet={avatarSrcSet} sizes="224px" />
                  )}
                  <img
                    src={asset(artisan.image)}
                    alt={artisan.name}
                    className="ap-avatar"
                    width="112"
                    height="112"
                  />
                </picture>
                <span className="ap-verified-dot" title="GI-Verified HunarLink Artisan">
                  <ShieldCheck size={14} />
                </span>
              </div>

              <div className="ap-identity-copy">
                <div className="ap-badge-row">
                  {artisan.featured && (
                    <span className="ap-badge ap-badge-master">
                      <IconSpark size={12} /> Master Artisan
                    </span>
                  )}
                  <span className="ap-badge ap-badge-gi">
                    <IconBadgeCheck size={12} /> GI Tier-{artisan.maxGiLevel} Verified
                  </span>
                </div>

                <h1 id="artisan-profile-name">{artisan.name}</h1>
                <p className="ap-headline">
                  {artisan.craft} &middot; {artisan.credential}
                </p>

                <div className="ap-rating-bar">
                  <span className="ap-rating-score">
                    <Star size={14} /> <strong>{artisan.avgRating.toFixed(1)}</strong>
                  </span>
                  <span className="ap-rating-count">
                    ({artisan.totalReviews} {artisan.totalReviews === 1 ? 'review' : 'reviews'})
                  </span>
                  <span className="ap-dot" aria-hidden="true">&bull;</span>
                  <span className="ap-rating-loc">
                    <IconMapPin size={13} /> {artisan.district}, Jammu &amp; Kashmir
                  </span>
                  <span className="ap-dot" aria-hidden="true">&bull;</span>
                  <span className="ap-rating-starting">
                    Starting at <strong>{formatINR(artisan.startingPrice)}</strong>
                  </span>
                </div>
              </div>
            </div>

            <dl className="ap-facts-strip">
              <div>
                <dt>From</dt>
                <dd>{artisan.district}, J&amp;K</dd>
              </div>
              <div>
                <dt>{artisan.since ? 'At the loom since' : 'Guild status'}</dt>
                <dd>{artisan.since ? artisan.since : 'Verified Atelier'}</dd>
              </div>
              <div>
                <dt>Avg. response time</dt>
                <dd>~2 hours</dd>
              </div>
              <div>
                <dt>Artisan payout</dt>
                <dd>100% Direct (0% Cut)</dd>
              </div>
            </dl>
          </section>

          {/* 2. About + GI Credentials + Skills */}
          <section className="ap-card ap-about-card" aria-labelledby="ap-about-heading">
            <h2 id="ap-about-heading">About this artisan</h2>
            <p className="ap-bio">{artisan.bio}</p>

            <div className="ap-subblock">
              <h3>Craft Specialties &amp; Techniques</h3>
              <div className="ap-skills-list">
                {artisan.guilds.map((g) => (
                  <Link
                    key={g.id}
                    to={`/category/${g.id}`}
                    className="ap-skill-chip ap-skill-chip-link"
                  >
                    {g.label}
                  </Link>
                ))}
                {artisan.techniques.map((t) => (
                  <span key={t} className="ap-skill-chip">
                    {t}
                  </span>
                ))}
                <span className="ap-skill-chip">GI Tier-{artisan.maxGiLevel}</span>
                <span className="ap-skill-chip">{artisan.district} Cluster</span>
              </div>
            </div>

            {artisan.giIds.length > 0 && (
              <div className="ap-subblock">
                <h3>Verified GI Registry Passports (Click to Verify)</h3>
                <div className="ap-gi-list">
                  {artisan.giIds.slice(0, 6).map((gi) => (
                    <button
                      key={gi}
                      type="button"
                      className="ap-gi-pill"
                      onClick={() => openModal('giVerify', { giId: gi, code: gi })}
                    >
                      <IconShield size={13} /> {gi}
                    </button>
                  ))}
                </div>
              </div>
            )}

            <div className="ap-subblock ap-lang-row">
              <span><strong>Languages:</strong> {artisan.languages.join(', ')}</span>
              <span>
                <strong>Combined craft time:</strong>{' '}
                {artisan.totalLoomHours.toLocaleString('en-IN')} loom / workshop hours
              </span>
            </div>
          </section>

          {/* 3. Fiverr-style "Crafts" Catalogue Grid */}
          <section className="ap-section" aria-labelledby="ap-crafts-heading">
            <div className="ap-section-head">
              <div>
                <p className="ap-kicker">DIRECT FROM THE WORKSHOP</p>
                <h2 id="ap-crafts-heading">
                  Crafts by {artisan.name} ({visibleListings.length})
                </h2>
              </div>

              <div className="ap-controls-row">
                {techniqueTabs.length > 1 && (
                  <div className="ap-filter-pills" role="tablist" aria-label="Filter by technique">
                    <button
                      type="button"
                      role="tab"
                      aria-selected={techFilter === 'all'}
                      className={`ap-filter-pill${techFilter === 'all' ? ' is-active' : ''}`}
                      onClick={() => setTechFilter('all')}
                    >
                      All ({artisan.listings.length})
                    </button>
                    {techniqueTabs.map(([tech, count]) => (
                      <button
                        key={tech}
                        type="button"
                        role="tab"
                        aria-selected={techFilter === tech}
                        className={`ap-filter-pill${techFilter === tech ? ' is-active' : ''}`}
                        onClick={() => setTechFilter(tech)}
                      >
                        {tech.charAt(0).toUpperCase() + tech.slice(1)} ({count})
                      </button>
                    ))}
                  </div>
                )}

                <label className="ap-sort-wrap">
                  <span className="sr-only">Sort crafts</span>
                  <select
                    value={sortBy}
                    onChange={(e) => setSortBy(e.target.value)}
                    aria-label="Sort crafts"
                  >
                    <option value="featured">Sort: Featured</option>
                    <option value="price-asc">Price: Low to High</option>
                    <option value="price-desc">Price: High to Low</option>
                    <option value="rating">Highest Rated</option>
                  </select>
                </label>
              </div>
            </div>

            <div className="ap-gigs-grid">
              {visibleListings.map((product) => (
                <ProductCard key={product.id} product={product} onBuyNow={handleBuyNow} />
              ))}
            </div>
          </section>

          {/* 4. Reviews & Breakdown */}
          <section className="ap-card ap-reviews-card" aria-labelledby="ap-reviews-heading">
            <div className="ap-reviews-head">
              <div>
                <h2 id="ap-reviews-heading">
                  Reviews for {artisan.name} ({artisan.totalReviews})
                </h2>
                <p className="ap-reviews-sub">
                  Verified collector impressions from HunarLink deliveries
                </p>
              </div>
              <button
                type="button"
                className="ap-btn ap-btn-outline ap-btn-sm"
                onClick={() => setReviewOpen((o) => !o)}
              >
                {reviewOpen ? 'Close form' : 'Write a review'}
              </button>
            </div>

            <div className="ap-rating-summary">
              <div className="ap-rating-big">
                <strong>{artisan.avgRating.toFixed(1)}</strong>
                <div className="ap-stars-row" aria-label={`${artisan.avgRating} out of 5 stars`}>
                  {Array.from({ length: 5 }).map((_, i) => (
                    <Star key={i} size={15} />
                  ))}
                </div>
                <span>{artisan.totalReviews} verified ratings</span>
              </div>

              <div className="ap-rating-bars">
                {ratingBreakdown.map((row) => (
                  <div className="ap-bar-row" key={row.stars}>
                    <span className="ap-bar-label">{row.stars} Stars</span>
                    <div className="ap-bar-track" aria-hidden="true">
                      <div className="ap-bar-fill" style={{ width: `${row.pct}%` }} />
                    </div>
                    <span className="ap-bar-count">({row.count})</span>
                  </div>
                ))}
              </div>
            </div>

            {reviewOpen && (
              <form className="ap-review-form" onSubmit={submitReview}>
                <div className="ap-form-grid">
                  <label>
                    <span>Your name</span>
                    <input
                      type="text"
                      required
                      placeholder="e.g. Aarav Mehta"
                      value={reviewDraft.author}
                      onChange={(e) => setReviewDraft((d) => ({ ...d, author: e.target.value }))}
                    />
                  </label>
                  <label>
                    <span>City</span>
                    <input
                      type="text"
                      placeholder="e.g. New Delhi"
                      value={reviewDraft.city}
                      onChange={(e) => setReviewDraft((d) => ({ ...d, city: e.target.value }))}
                    />
                  </label>
                  <label>
                    <span>Piece reviewed</span>
                    <select
                      value={reviewDraft.productId || artisan.topProduct?.id || ''}
                      onChange={(e) =>
                        setReviewDraft((d) => ({ ...d, productId: e.target.value }))
                      }
                    >
                      {artisan.listings.map((p) => (
                        <option key={p.id} value={p.id}>
                          {p.title}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    <span>Rating</span>
                    <select
                      value={reviewDraft.stars}
                      onChange={(e) => setReviewDraft((d) => ({ ...d, stars: Number(e.target.value) }))}
                    >
                      <option value={5}>5 Stars — Exceptional</option>
                      <option value={4}>4 Stars — Very Good</option>
                      <option value={3}>3 Stars — Good</option>
                    </select>
                  </label>
                </div>
                <label className="ap-form-full">
                  <span>Your review</span>
                  <textarea
                    rows={3}
                    required
                    placeholder={`Share your experience with ${artisan.name}'s craft...`}
                    value={reviewDraft.text}
                    onChange={(e) => setReviewDraft((d) => ({ ...d, text: e.target.value }))}
                  />
                </label>
                <div className="ap-form-actions">
                  <button type="submit" className="ap-btn ap-btn-primary ap-btn-sm">
                    Publish Review
                  </button>
                </div>
              </form>
            )}

            {artisan.reviews.length > 0 ? (
              <div className="ap-review-list">
                {artisan.reviews.map((rev) => (
                  <article className="ap-review-item" key={rev.id}>
                    <div className="ap-review-top">
                      <div className="ap-reviewer">
                        <span className="ap-reviewer-badge" aria-hidden="true">
                          {(rev.author || 'C')[0].toUpperCase()}
                        </span>
                        <div>
                          <strong>{rev.author}</strong>
                          <span className="ap-reviewer-meta">
                            {rev.city} &middot; {rev.date}
                          </span>
                        </div>
                      </div>
                      <div className="ap-review-stars" aria-label={`${rev.stars} out of 5 stars`}>
                        {Array.from({ length: Math.min(5, Math.max(1, rev.stars)) }).map((_, i) => (
                          <Star key={i} size={12} />
                        ))}
                        <span>{rev.stars}.0</span>
                      </div>
                    </div>
                    <p className="ap-review-body">{rev.text}</p>
                    {rev.productTitle && (
                      <div className="ap-review-piece">
                        Piece:{' '}
                        {rev.productId ? (
                          <Link to={productProfileHref(rev.productId)}>
                            {rev.productTitle}
                          </Link>
                        ) : (
                          rev.productTitle
                        )}
                      </div>
                    )}
                  </article>
                ))}
              </div>
            ) : (
              <p className="ap-review-empty">
                No written reviews yet for this workshop &mdash; click{' '}
                <strong>Write a review</strong> above to be the first collector to share your
                impression.
              </p>
            )}
          </section>

          {/* 5. Similar Artisans */}
          {similarArtisans.length > 0 && (
            <section className="ap-section" aria-labelledby="ap-similar-heading">
              <div className="ap-section-head">
                <div>
                  <p className="ap-kicker">EXPLORE MORE WORKSHOPS</p>
                  <h2 id="ap-similar-heading">Similar Master Artisans</h2>
                </div>
                <Link to="/artisans" className="ap-see-all">
                  View all {allArtisans.length} artisans &rarr;
                </Link>
              </div>

              <div className="ap-similar-grid">
                {similarArtisans.map((other) => (
                  <Link
                    key={other.id}
                    to={artisanProfileHref(other)}
                    className="ap-similar-card"
                  >
                    <div className="ap-similar-thumb">
                      <img
                        src={asset(other.image)}
                        alt={other.name}
                        width="320"
                        height="200"
                        loading="lazy"
                        decoding="async"
                      />
                    </div>
                    <div className="ap-similar-body">
                      <span className="ap-similar-craft">{other.craft}</span>
                      <h3>{other.name}</h3>
                      <div className="ap-similar-meta">
                        <span>
                          <Star size={11} /> {other.avgRating.toFixed(1)} ({other.totalReviews})
                        </span>
                        <span>From {formatINR(other.startingPrice)}</span>
                      </div>
                    </div>
                  </Link>
                ))}
              </div>
            </section>
          )}
        </div>

        {/* ======================== RIGHT STICKY SIDEBAR ======================== */}
        <aside className="ap-sidebar" aria-label="Contact artisan and workshop summary">
          <div className="ap-sticky">
            <div className="ap-card ap-contact-card">
              <div className="ap-mini-profile">
                <img
                  src={asset(artisan.image)}
                  alt=""
                  className="ap-mini-avatar"
                  width="48"
                  height="48"
                />
                <div>
                  <strong>{artisan.name}</strong>
                  <span className="ap-status-line">
                    <span className="ap-online-dot" aria-hidden="true" />
                    Accepting direct &amp; custom orders
                  </span>
                </div>
              </div>

              <p className="ap-contact-note">
                Message {artisan.name} directly for provenance questions, custom dimensions,
                monogramming, or heirloom commissions.
              </p>

              <button
                type="button"
                className="ap-btn ap-btn-primary ap-btn-block"
                onClick={() => {
                  setContactOpen((o) => !o);
                  setContactSent(false);
                }}
              >
                <IconChat size={16} />
                <span>{contactOpen ? 'Hide Message Form' : 'Contact Artisan'}</span>
              </button>

              {contactOpen && (
                <form className="ap-contact-form" onSubmit={submitContact}>
                  {contactSent && (
                    <div className="ap-contact-sent" role="status">
                      Sent! Your inquiry is now in {artisan.name}&rsquo;s Seller Portal inbox.
                    </div>
                  )}
                  <label>
                    <span>Your name</span>
                    <input
                      type="text"
                      required
                      placeholder="Your full name"
                      value={contactForm.name}
                      onChange={(e) => setContactForm((f) => ({ ...f, name: e.target.value }))}
                    />
                  </label>
                  <label>
                    <span>Email or phone</span>
                    <input
                      type="text"
                      required
                      placeholder="you@example.com or +91 ..."
                      value={contactForm.contact}
                      onChange={(e) => setContactForm((f) => ({ ...f, contact: e.target.value }))}
                    />
                  </label>
                  <label>
                    <span>Regarding</span>
                    <select
                      value={contactForm.piece}
                      onChange={(e) => setContactForm((f) => ({ ...f, piece: e.target.value }))}
                    >
                      <option value="custom">Custom / Bespoke Commission</option>
                      {artisan.listings.map((p) => (
                        <option key={p.id} value={p.id}>
                          {p.title} ({formatINR(p.price)})
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    <span>Message</span>
                    <textarea
                      rows={3}
                      required
                      placeholder="Ask about GI certification, weave time, custom colours, or shipping..."
                      value={contactForm.message}
                      onChange={(e) => setContactForm((f) => ({ ...f, message: e.target.value }))}
                    />
                  </label>
                  <button type="submit" className="ap-btn ap-btn-orange ap-btn-block">
                    Send Direct Message
                  </button>
                </form>
              )}

              <div className="ap-secondary-actions">
                <button
                  type="button"
                  className="ap-btn ap-btn-outline ap-btn-block"
                  onClick={() => navigate('/wholesale')}
                >
                  Request Wholesale Lot
                </button>
              </div>
            </div>

            <div className="ap-card ap-snapshot-card">
              <h3>Atelier Snapshot</h3>
              <dl className="ap-snapshot-list">
                <div>
                  <dt>Starting price</dt>
                  <dd>{formatINR(artisan.startingPrice)}</dd>
                </div>
                <div>
                  <dt>Active listings</dt>
                  <dd>{artisan.listingCount}</dd>
                </div>
                <div>
                  <dt>Loom hours logged</dt>
                  <dd>{artisan.totalLoomHours.toLocaleString('en-IN')} hrs</dd>
                </div>
                <div>
                  <dt>GI Passports</dt>
                  <dd>{artisan.giIds.length} verified</dd>
                </div>
                <div>
                  <dt>Workshop cluster</dt>
                  <dd>{artisan.district}, Kashmir</dd>
                </div>
              </dl>

              <ul className="ap-trust-list">
                <li>
                  <IconRupeeCoin size={16} />
                  <span>100% direct artisan payout &mdash; zero middleman cut</span>
                </li>
                <li>
                  <IconShield size={16} />
                  <span>Verified Razorpay checkout &amp; GI provenance tag</span>
                </li>
                <li>
                  <IconTruck size={16} />
                  <span>Insured museum-grade packaging worldwide</span>
                </li>
              </ul>
            </div>
          </div>
        </aside>
      </div>
    </main>
  );
}
