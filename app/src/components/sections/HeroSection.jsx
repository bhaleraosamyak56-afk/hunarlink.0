import React, { useEffect, useState } from 'react';
import { srcSetFor, hdSrcFor } from '../../data/imageVariants.js';
import { useNavigate } from 'react-router-dom';
import { useStore } from '../../state/StoreContext.jsx';
import { asset, formatINR } from '../../utils/legacy.js';
import { IconBadgeCheck, IconMapPin, IconRupeeCoin, IconSearchScan, IconShield } from '../../components/LineIcons.jsx';
import { scrollToSection } from '../../utils/scrollToSection.js';

/* ==========================================================================
   HeroSection
   --------------------------------------------------------------------------
   Left column: credential ribbon, overline, the rotating location pill, the
   headline, two calls to action, and the artisan proof row. Right column: the
   three-card bento collage. Below: the four-KPI trust bar.

   The location pill cycles through five phrases — a plain interval, with the
   active class swapped rather than the text rewritten.
   ========================================================================== */

const PLACES = [
  'Jammu & Kashmir',
  'Kashmir Handicrafts',
  'GI-Certified Crafts',
  'Handmade in Srinagar',
  'Pashmina \u00b7 Walnut \u00b7 Kani'
];

const BENTO = [
  {
    id: 'hl-pash-002',
    img: 'image_2.jpg',
    alt: 'Jamawar Heirloom Stole',
    main: true,
    pill: 'GI Certified Loom #108',
    kicker: 'Kani Masterweave \u2022 Srinagar',
    name: 'Jamawar Heirloom Stole'
  },
  {
    id: 'hl-waln-007',
    img: 'image_3.jpg',
    alt: 'Walnut Wood Lattice Carving',
    pill: 'GI Walnut',
    kicker: '300-Yr Seasoned Timber',
    name: 'Lattice Carving'
  },
  {
    id: 'hl-papr-008',
    img: 'image_4.jpg',
    alt: 'Persian Guldan Papier-Mache',
    pill: '24K Naqash',
    kicker: 'Hand-Painted Lacquer',
    name: 'Persian Guldan'
  }
];

export default function HeroSection() {
  const navigate = useNavigate();
  const { openModal, openDrawer, productById } = useStore();

  /* The price and UUID on each feature card are resolved from the live DB catalogue. */
  const featurePrice = productById(BENTO[0].id)?.price;
  const openBentoProduct = (legacyCode) => {
    const match = productById(legacyCode);
    const targetId = match ? match.id : legacyCode;
    navigate(`/product?id=${encodeURIComponent(targetId)}`);
  };
  const [place, setPlace] = useState(0);

  useEffect(() => {
    const t = setInterval(() => setPlace((i) => (i + 1) % PLACES.length), 2600);
    return () => clearInterval(t);
  }, []);

  const scrollTo = (id) => scrollToSection(id);

  return (
    <section className="hero-section" id="hero-section">
      {/* Craftsmen at work, low opacity, behind the whole hero. Decorative
          only: aria-hidden, and the hero copy sits on translucent panels so
          the only thing the photograph touches directly is empty margin. */}
      {/* These are CSS background-image layers rather than <img> elements.
          Chrome reports the largest *painted* image as LCP, and at 0.1–0.2
          opacity these three were being named as the LCP element at 12–13 s
          even though the real content (the h1) paints in ~1 s. As background
          images they are not LCP candidates, so LCP measures the headline the
          design actually leads with. Resolve via asset() so both localhost (/)
          and GitHub Pages (/hunarlink/) load the WebP variants cleanly. */}
      <div className="hero-atmosphere" aria-hidden="true">
        <span
          className="ha-img ha-1"
          style={{ backgroundImage: `url("${hdSrcFor('img/artisans/artisan-02.jpg')}")` }}
        />
        <span
          className="ha-img ha-2"
          style={{ backgroundImage: `url("${hdSrcFor('img/artisans/artisan-03.jpg')}")` }}
        />
        <span
          className="ha-img ha-3"
          style={{ backgroundImage: `url("${hdSrcFor('img/artisans/artisan-05.jpg')}")` }}
        />
      </div>
      <div className="container">
        <div className="hero-grid">
          <div className="hero-left">
            <div className="hero-copy">
            <div className="cred-ribbon">
              <span className="cr-dot" aria-hidden="true" />
              <b>GI-Certified</b>
              <span className="cr-sep" aria-hidden="true">
                &#9670;
              </span>
              <b>Razorpay Protected</b>
              <span className="cr-sep" aria-hidden="true">
                &#9670;
              </span>
              <b>Shipped Worldwide</b>
            </div>

            <div className="hero-overline">
              GI-CERTIFIED VALLEY CRAFT MARKETPLACE &bull; TEAM 16
            </div>

            <div className="hero-location-pill">
              <span className="pill-pin" aria-hidden="true" />
              <span className="loc-rotor" aria-hidden="true">
                {PLACES.map((p, i) => (
                  <span
                    key={p}
                    className={`loc-item${i === place ? ' is-active' : ''}`}
                  >
                    {p}
                  </span>
                ))}
              </span>
              <span className="sr-only">
                Srinagar, Jammu &amp; Kashmir — Kashmir handicrafts, GI-certified crafts, pashmina,
                walnut and Kani
              </span>
            </div>

            <h1 className="hero-title">
              Explore Timeless <em>Indian Crafts</em>
            </h1>

            <div className="hero-cta-row">
              <button
                type="button"
                className="btn-primary-forest"
                id="hero-explore-btn"
                onClick={() => scrollTo('marketplace-section')}
              >
                <span>Explore Crafts</span>
                <span>&rarr;</span>
              </button>
              <button
                type="button"
                className="btn-outline-ivory"
                id="hero-verify-btn"
                onClick={() => openModal('giVerify', { giId: 'GI-JK-PASH-8810' })}
              >
                <span><IconShield size={15} /></span>
                <span>Verify GI Tag / QR</span>
              </button>
            </div>

            <div className="hero-artisan-proof">
              <picture>
                {srcSetFor('assets/image_1.jpg') && (
                  <source type="image/webp" srcSet={srcSetFor('assets/image_1.jpg')} sizes="120px" />
                )}
                <img
                  src={asset('assets/image_1.jpg')}
                  alt="Registered Kashmiri Artisans"
                  className="proof-thumb"
                />
              </picture>
              <div>
                <div className="proof-title">2,400+ Registered Artisans</div>
                <div className="proof-sub">
                  Direct payout to geo-verified workshops across Srinagar, Budgam &amp; Anantnag
                </div>
              </div>
            </div>
            </div>
          </div>

          <div className="hero-bento">
            {BENTO.map((b) => (
              <button
                type="button"
                key={b.id}
                className={`bento-card${b.main ? ' bento-main' : ''}`}
                onClick={() => openBentoProduct(b.id)}
              >
                {/* Full-HD WebP srcSet with Retina-aware sizes so the hero
                    centerpiece and flanking craft cards render razor-sharp. */}
                <picture>
                  {srcSetFor(`assets/${b.img}`) && (
                    <source
                      type="image/webp"
                      srcSet={srcSetFor(`assets/${b.img}`)}
                      sizes={b.main ? '(max-width: 760px) 100vw, 52vw' : '(max-width: 760px) 50vw, 32vw'}
                    />
                  )}
                  <img
                    src={asset(`assets/${b.img}`)}
                    alt={b.alt}
                    width={b.main ? '640' : '320'}
                    height={b.main ? '300' : '210'}
                    loading={b.main ? undefined : 'lazy'}
                    decoding={b.main ? undefined : 'async'}
                    fetchPriority={b.main ? 'high' : undefined}
                  />
                </picture>
                <div className="bento-overlay">
                  <span className="bento-top-pill">
                    {b.pill}
                    {b.main && featurePrice ? ` \u2022 ${formatINR(featurePrice)}` : ''}
                  </span>
                  <div>
                    <span className="bento-kicker">{b.kicker}</span>
                    <div className="bento-name">{b.name}</div>
                  </div>
                </div>
              </button>
            ))}
          </div>
        </div>

        <div className="trust-bar">
          <button
            type="button"
            className="trust-item"
            onClick={() => scrollTo('artisan-showcase-section')}
          >
            <div className="trust-icon-box"><IconBadgeCheck size={16} /></div>
            <div>
              <div className="trust-value">2,400+</div>
              <div className="trust-label">Direct Valley Artisans</div>
            </div>
          </button>

          <button
            type="button"
            className="trust-item"
            onClick={() => openModal('giVerify', { giId: 'GI-JK-PASH-8821' })}
          >
            <div className="trust-icon-box"><IconMapPin size={15} /></div>
            <div>
              <div className="trust-value">100% Origin</div>
              <div className="trust-label">Geo-Tagged Looms</div>
            </div>
          </button>

          <button
            type="button"
            className="trust-item"
            onClick={() => scrollTo('verification-section')}
          >
            <div className="trust-icon-box"><IconSearchScan size={15} /></div>
            <div>
              <div className="trust-value">3-Layer GI</div>
              <div className="trust-label">Automated Lab Audit</div>
            </div>
          </button>

          <button
            type="button"
            className="trust-item"
            onClick={() => openDrawer('cart')}
          >
            <div className="trust-icon-box"><IconRupeeCoin size={18} /></div>
            <div>
              <div className="trust-value">Zero Cut</div>
              <div className="trust-label">Direct Artisan Payouts</div>
            </div>
          </button>
        </div>
      </div>
    </section>
  );
}
