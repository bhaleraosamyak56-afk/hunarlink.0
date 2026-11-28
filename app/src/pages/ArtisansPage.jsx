import React, { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { srcSetFor } from '../data/imageVariants.js';
import { useStore } from '../state/StoreContext.jsx';
import { artisanProfileHref, collectArtisans } from '../utils/artisans.js';
import { asset, formatINR } from '../utils/legacy.js';
import { Star } from '../components/Icons.jsx';
import '../styles/artisan-directory.css';

/* ==========================================================================
   ArtisansPage — /artisans
   --------------------------------------------------------------------------
   Searchable, filterable directory of all verified artisans hydrated from the
   HunarLink database (`seller_profiles` + `seller_product_listings`).
   Clicking any card opens their dedicated profile by unique database UUID:
   `/artisan?id=<seller_profile_id>`.
   ========================================================================== */

export default function ArtisansPage() {
  const { catalogue, artisans: dbArtisans, reviews, dbSyncStatus } = useStore();
  const [guildFilter, setGuildFilter] = useState('all');
  const [query, setQuery] = useState('');

  const artisans = useMemo(
    () => collectArtisans(catalogue, reviews, dbArtisans),
    [catalogue, reviews, dbArtisans]
  );

  const guildOptions = useMemo(() => {
    const map = new Map();
    for (const a of artisans) {
      for (const g of a.guilds) {
        if (!map.has(g.id)) map.set(g.id, { id: g.id, label: g.label, count: 0 });
        map.get(g.id).count += 1;
      }
    }
    return [...map.values()];
  }, [artisans]);

  const filtered = useMemo(() => {
    const term = query.trim().toLowerCase();
    return artisans.filter((a) => {
      if (guildFilter !== 'all' && !a.guilds.some((g) => g.id === guildFilter)) {
        return false;
      }
      if (!term) return true;
      return (
        a.name.toLowerCase().includes(term) ||
        a.craft.toLowerCase().includes(term) ||
        a.district.toLowerCase().includes(term) ||
        a.skills.some((s) => s.toLowerCase().includes(term))
      );
    });
  }, [artisans, guildFilter, query]);

  return (
    <main className="artisan-directory-page" id="main-content">
      <section className="artisan-directory-hero" aria-labelledby="artisan-directory-title">
        <div className="container artisan-directory-wrap">
          <Link className="artisan-directory-back" to="/">
            <span aria-hidden="true">&larr;</span> Back to HunarLink
          </Link>
          <div className="artisan-directory-heading">
            <div>
              <p className="artisan-directory-kicker">THE HANDS BEHIND THE HEIRLOOMS</p>
              <h1 id="artisan-directory-title">Our Artisans</h1>
              <p className="artisan-directory-intro">
                Select any master artisan to open their full workshop profile, inspect GI
                passports, browse their pieces, read collector reviews, or message them directly.
              </p>
            </div>
            <div className="artisan-directory-count" aria-live="polite">
              <strong>{filtered.length}</strong>
              <span>{filtered.length === 1 ? 'artisan' : 'artisans'}</span>
            </div>
          </div>

          <div className="artisan-directory-toolbar">
            <div className="artisan-directory-pills" role="tablist" aria-label="Filter by craft guild">
              <button
                type="button"
                role="tab"
                aria-selected={guildFilter === 'all'}
                className={`artisan-directory-pill${guildFilter === 'all' ? ' is-active' : ''}`}
                onClick={() => setGuildFilter('all')}
              >
                All Guilds ({artisans.length})
              </button>
              {guildOptions.map((g) => (
                <button
                  key={g.id}
                  type="button"
                  role="tab"
                  aria-selected={guildFilter === g.id}
                  className={`artisan-directory-pill${guildFilter === g.id ? ' is-active' : ''}`}
                  onClick={() => setGuildFilter(g.id)}
                >
                  {g.label} ({g.count})
                </button>
              ))}
            </div>

            <label className="artisan-directory-search">
              <span className="sr-only">Search artisans by name, craft, or district</span>
              <input
                type="search"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search artisan, craft, or district..."
              />
            </label>
          </div>
        </div>
      </section>

      <section className="artisan-directory-list" aria-label="Artisan directory">
        <div className="container artisan-directory-wrap">
          {dbSyncStatus === 'loading' && artisans.length === 0 ? (
            <div className="artisan-directory-empty">
              <p>Loading verified artisans from the HunarLink database&hellip;</p>
            </div>
          ) : filtered.length ? (
            <div className="artisan-directory-grid">
              {filtered.map((artisan) => {
                const srcSet = srcSetFor(artisan.image);
                return (
                  <Link
                    to={artisanProfileHref(artisan)}
                    className="artisan-directory-card"
                    key={artisan.id}
                    data-artisan-id={artisan.id}
                  >
                    <div className="artisan-directory-image">
                      <picture>
                        {srcSet && (
                          <source
                            type="image/webp"
                            srcSet={srcSet}
                            sizes="(max-width: 640px) 100vw, (max-width: 1000px) 50vw, 34vw"
                          />
                        )}
                        <img
                          src={asset(artisan.image)}
                          alt={
                            artisan.featured
                              ? `${artisan.name} at work`
                              : `${artisan.craft} by ${artisan.name}`
                          }
                          width="480"
                          height="300"
                          loading="lazy"
                          decoding="async"
                        />
                      </picture>
                      {artisan.featured && (
                        <span className="artisan-directory-featured">Featured master</span>
                      )}
                      <span className="artisan-directory-rating">
                        <Star size={11} /> {artisan.avgRating.toFixed(1)} ({artisan.totalReviews})
                      </span>
                    </div>
                    <div className="artisan-directory-card-body">
                      <p className="artisan-directory-craft">{artisan.craft}</p>
                      <h2>{artisan.name}</h2>
                      <p className="artisan-directory-loc">
                        {artisan.district}, Kashmir &bull; {artisan.listingCount}{' '}
                        {artisan.listingCount === 1 ? 'listing' : 'listings'}
                      </p>
                      <div className="artisan-directory-meta">
                        <span className="artisan-directory-price">
                          From <strong>{formatINR(artisan.startingPrice)}</strong>
                        </span>
                        <span className="artisan-directory-cta">
                          View profile <span aria-hidden="true">&rarr;</span>
                        </span>
                      </div>
                    </div>
                  </Link>
                );
              })}
            </div>
          ) : (
            <div className="artisan-directory-empty">
              <p>No artisans matched your filter.</p>
              <button
                type="button"
                className="artisan-directory-reset"
                onClick={() => {
                  setGuildFilter('all');
                  setQuery('');
                }}
              >
                Reset filters
              </button>
            </div>
          )}
        </div>
      </section>
    </main>
  );
}
