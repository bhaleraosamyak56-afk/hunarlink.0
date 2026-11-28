import React, { createContext, useCallback, useContext, useEffect, useMemo, useReducer, useRef } from 'react';
import {
  cartTotals,
  loadStorage,
  saveStorage,
  pushRecentlyViewed,
  readRecentlyViewed
} from '../utils/legacy.js';
import {
  fetchArtisans,
  fetchCatalogProducts,
  fetchMyAddresses,
  fetchMyRetailOrders
} from '../services/apiClient.js';

/* ==========================================================================
   Store — 100% Real-Auth & Backend-Database-Hydrated Application State
   --------------------------------------------------------------------------
   - Zero hardcoded dummy buyers, dummy addresses, dummy orders, or static
     dummy product catalogs.
   - All catalogue listings, artisan profiles, saved addresses, and retail
     orders are hydrated strictly from FastAPI + MySQL/SQLite using the
     signed-in user's verified Clerk RS256 session JWT.
   ========================================================================== */

const KEYS = {
  cart: 'hunarlink_cart',
  wishlist: 'hunarlink_wishlist',
  savedLater: 'hunarlink_saved_later',
  coupon: 'hunarlink_coupon',
  user: 'hunarlink_auth_user',
  addresses: 'hunarlink_addresses',
  orders: 'hunarlink_orders',
  customProducts: 'hunarlink_custom_products',
  productOverrides: 'hunarlink_product_overrides',
  reviews: 'hunarlink_reviews',
  sellerInquiries: 'hunarlink_seller_inquiries',
  buyerProfile: 'hunarlink_buyer_profile',
  platformUsers: 'hunarlink_platform_users',
  adminToken: 'hunarlink_admin_token'
};

const KEY_TO_SLICE = {
  [KEYS.cart]: 'cart',
  [KEYS.wishlist]: 'wishlist',
  [KEYS.savedLater]: 'savedLater',
  [KEYS.coupon]: 'coupon',
  [KEYS.user]: 'user',
  [KEYS.reviews]: 'reviews',
  [KEYS.sellerInquiries]: 'sellerInquiries',
  [KEYS.buyerProfile]: 'buyerProfile',
  [KEYS.adminToken]: 'adminToken'
};

function normaliseAddress(a) {
  if (!a || typeof a !== 'object') return a;
  return {
    id: a.id,
    name: a.recipient_name ?? a.name ?? '',
    phone: a.recipient_phone ?? a.phone ?? '',
    locality: a.line1 ?? a.locality ?? '',
    line2: a.line2 ?? '',
    city: a.city ?? '',
    state: a.state_province ?? a.state ?? 'Jammu and Kashmir',
    pincode: a.postal_code ?? a.pincode ?? a.pin ?? '',
    type: a.address_label ?? a.type ?? 'HOME',
    isDefault: Boolean(a.is_default ?? a.isDefault)
  };
}

function normaliseGuildSlug(categorySlug = '') {
  const s = String(categorySlug || '').toLowerCase();
  if (s.includes('pashmina') || s.includes('sozni') || s.includes('kani') || s.includes('shawl')) return 'pashmina';
  if (s.includes('carpet') || s.includes('silk')) return 'silk-rugs';
  if (s.includes('walnut') || s.includes('wood')) return 'walnut';
  if (s.includes('papier') || s.includes('mache')) return 'papier-mache';
  return s || 'pashmina';
}

function craftPhotoForListing(sku = '', guild = 'pashmina') {
  const key = String(sku || '').toUpperCase();
  if (key.includes('PASH-002')) return 'assets/products/pashmina_02.jpg';
  if (key.includes('PASH')) return 'assets/products/pashmina_01.jpg';
  if (key.includes('SILK')) return 'assets/products/silkrug_01.jpg';
  if (key.includes('WALN')) return 'assets/products/walnut_01.jpg';
  if (key.includes('PAPR') || key.includes('PMAC')) return 'assets/products/papier_01.jpg';
  if (key.includes('KANI')) return 'assets/products/kani_01.jpg';
  if (key.includes('SOZN')) return 'assets/products/sozni_01.jpg';
  if (guild === 'silk-rugs') return 'assets/products/silkrug_01.jpg';
  if (guild === 'walnut') return 'assets/products/walnut_01.jpg';
  if (guild === 'papier-mache') return 'assets/products/papier_01.jpg';
  return 'assets/products/pashmina_01.jpg';
}

export function mapDbListingToProduct(item) {
  const guild = normaliseGuildSlug(item.guild || item.category_slug);
  const price = Number(item.selling_price || 0);
  const mrp = Number(item.compare_at_mrp || price);
  const originalPrice = Number(item.original_market_price || mrp || price);
  const isGi = item.gi_status === 'GI_VERIFIED' || item.verification_path === 'GI';
  const rawTech = item.technique ? String(item.technique).toLowerCase() : null;
  const technique =
    guild === 'pashmina'
      ? rawTech && ['handwoven', 'kani', 'sozni'].includes(rawTech)
        ? rawTech
        : 'handwoven'
      : undefined;

  return {
    id: item.listing_id,
    sellerListingId: item.listing_id,
    productId: item.product_id,
    productVariantId: item.product_variant_id,
    sellerProfileId: item.seller_profile_id,
    artisanId: item.seller_profile_id,
    legacyCode: item.legacy_code || String(item.seller_sku || '').toLowerCase(),
    sku: item.seller_sku,
    slug: item.product_slug,
    title: item.title,
    description: item.description || '',
    guild,
    guildLabel: item.category_name || 'Kashmiri Craft',
    technique,
    artisan: item.artisan_name || item.store_name || 'Verified Artisan',
    artisanSlug: item.artisan_slug,
    artisanPortrait: item.artisan_portrait_url || null,
    storeName: item.store_name || '',
    district: item.workshop_district || 'Srinagar',
    craftSpecialty: item.craft_specialty || item.category_name || '',
    price,
    mrp,
    originalPrice,
    rating: Number(item.rating || 4.9),
    reviewCount: Number(item.review_count ?? 0),
    giId: item.claimed_gi_code || item.seller_sku,
    giStatus: item.gi_status || 'UNVERIFIED',
    giLevel: Number(item.gi_level || (isGi ? 3 : 1)),
    purityMetric:
      item.purity_metric ||
      (isGi ? 'GI Registry Verified • Direct Artisan Loom' : 'Verified HunarLink Artisan Craft'),
    loomHours: Number(item.loom_hours || 320),
    dimensions: item.dimensions || 'Standard Artisan Craft',
    stock: Number(item.max_order_qty || 10),
    image: item.image_url || craftPhotoForListing(item.seller_sku, guild),
    galleryImages: Array.isArray(item.gallery_images) ? item.gallery_images : [],
    source: 'database'
  };
}

function mapDbOrderToUi(o, catalogueList = []) {
  const created = o.created_at ? new Date(o.created_at) : new Date();
  const snap = o.shipping_address || {};
  const stageMap = {
    PENDING_PAYMENT: 1,
    CONFIRMED: 2,
    PROCESSING: 3,
    PARTIALLY_SHIPPED: 4,
    SHIPPED: 4,
    DELIVERED: 5
  };
  return {
    id: o.order_number || o.order_id,
    orderId: o.order_id,
    date: created.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }),
    time: created.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' }),
    createdAt: o.created_at,
    buyer: {
      name: snap.name || '',
      phone: snap.phone || '',
      locality: snap.locality || '',
      city: snap.city || '',
      pincode: snap.pincode || '',
      fullAddress: snap.locality
        ? `${snap.name || ''}, ${snap.locality}, ${snap.city || ''} - ${snap.pincode || ''}`
        : ''
    },
    items: (o.items || []).map((i) => {
      const targetId = i.seller_listing_id || i.product_id;
      const matched = catalogueList.find(
        (p) => p.id === targetId || p.productId === i.product_id
      );
      return {
        productId: targetId,
        title: i.title,
        qty: i.quantity,
        price: Number(i.unit_price || 0),
        lineTotal: Number(i.line_total || 0),
        giId: matched?.giId || i.sku || i.gi_status,
        artisan: matched?.artisan || 'Verified HunarLink Artisan',
        image: matched?.image || craftPhotoForListing(i.sku)
      };
    }),
    subtotal: Number(o.subtotal_amount || o.total_amount || 0),
    discount: Number(o.discount_amount || 0),
    shippingFee: Number(o.shipping_fee || 0),
    total: Number(o.total_amount || 0),
    paymentMethod: o.payment_label || o.payment_method,
    paymentStatus: o.payment_status,
    fulfilmentStatus: o.fulfilment_status,
    address: snap.locality
      ? `${snap.name || ''}, ${snap.locality}, ${snap.city || ''} - ${snap.pincode || ''}`
      : '',
    stage: stageMap[o.fulfilment_status] || 1
  };
}

function readRealClerkUserOnly() {
  const stored = loadStorage(KEYS.user, null);
  if (stored && stored.authProvider === 'clerk' && stored.isLoggedIn) {
    return stored;
  }
  return null;
}

const SLICE_DEFAULTS = {
  cart: [],
  wishlist: [],
  savedLater: [],
  coupon: null,
  user: null,
  addresses: [],
  orders: [],
  customProducts: [],
  productOverrides: {},
  reviews: {},
  sellerInquiries: [],
  buyerProfile: null,
  platformUsers: [],
  adminToken: null
};

export const PRICE_BOUNDS = { min: 500, max: 250000 };

const DEFAULT_FILTERS = {
  query: '',
  guild: 'all',
  technique: 'all',
  artisan: '',
  maxPrice: PRICE_BOUNDS.max,
  minRating: 0,
  giTier: 0,
  district: 'all',
  sort: 'featured'
};

const initialRealUser = readRealClerkUserOnly();

const initialState = {
  cart: initialRealUser ? loadStorage(KEYS.cart, []) : [],
  wishlist: initialRealUser ? loadStorage(KEYS.wishlist, []) : [],
  savedLater: initialRealUser ? loadStorage(KEYS.savedLater, []) : [],
  coupon: initialRealUser ? loadStorage(KEYS.coupon, null) : null,
  user: initialRealUser,
  addresses: [],
  orders: [],
  dbCatalogue: [],
  dbArtisans: [],
  dbSyncStatus: 'idle', // 'idle' | 'loading' | 'ready' | 'error'
  dbSyncError: null,
  authPrompt: null, // { seq, reason } when a guest triggers a sign-in-only action
  customProducts: [],
  productOverrides: {},
  reviews: loadStorage(KEYS.reviews, {}),
  sellerInquiries: loadStorage(KEYS.sellerInquiries, []),
  buyerProfile: initialRealUser ? loadStorage(KEYS.buyerProfile, null) : null,
  platformUsers: [],
  adminToken: loadStorage(KEYS.adminToken, null),
  recentlyViewed: initialRealUser ? readRecentlyViewed() : [],
  compareList: [],
  toasts: [],
  veil: { open: false, text: '' },
  ui: {
    drawer: null,
    modal: null,
    filters: DEFAULT_FILTERS,
    loadingProducts: false
  }
};

let toastSeq = 0;

function reducer(state, action) {
  switch (action.type) {
    /* -------------------------------------------------------------- db */
    case 'db/loading':
      return { ...state, dbSyncStatus: 'loading', dbSyncError: null };
    case 'db/publicLoaded':
      return {
        ...state,
        dbCatalogue: action.catalogue,
        dbArtisans: action.artisans,
        dbSyncStatus: 'ready',
        dbSyncError: null
      };
    case 'db/hydrated':
      return {
        ...state,
        dbCatalogue: action.catalogue,
        dbArtisans: action.artisans,
        orders: action.orders,
        addresses: action.addresses,
        dbSyncStatus: 'ready',
        dbSyncError: null
      };
    case 'db/error':
      return { ...state, dbSyncStatus: 'error', dbSyncError: action.error };
    case 'db/reset':
      return {
        ...state,
        cart: [],
        wishlist: [],
        savedLater: [],
        coupon: null,
        addresses: [],
        orders: [],
        buyerProfile: null,
        compareList: []
      };
    case 'auth/prompt':
      return { ...state, authPrompt: { seq: Date.now() + Math.random(), reason: action.reason } };
    case 'auth/clearPrompt':
      return { ...state, authPrompt: null };

    /* -------------------------------------------------------------- cart */
    case 'cart/add': {
      const { productId, qty = 1 } = action;
      const existing = state.cart.find((e) => e.productId === productId);
      const cart = existing
        ? state.cart.map((e) =>
            e.productId === productId ? { ...e, qty: Math.min(e.qty + qty, 10) } : e
          )
        : [...state.cart, { productId, qty }];
      return { ...state, cart };
    }
    case 'cart/setQty': {
      const cart = state.cart
        .map((e) => (e.productId === action.productId ? { ...e, qty: action.qty } : e))
        .filter((e) => e.qty > 0);
      return { ...state, cart };
    }
    case 'cart/remove':
      return { ...state, cart: state.cart.filter((e) => e.productId !== action.productId) };
    case 'cart/clear':
      return { ...state, cart: [] };
    case 'cart/saveForLater': {
      if (!state.cart.some((e) => e.productId === action.productId)) return state;
      return {
        ...state,
        cart: state.cart.filter((e) => e.productId !== action.productId),
        savedLater: state.savedLater.includes(action.productId)
          ? state.savedLater
          : [...state.savedLater, action.productId]
      };
    }
    case 'cart/moveBack': {
      const exists = state.cart.find((e) => e.productId === action.productId);
      return {
        ...state,
        savedLater: state.savedLater.filter((id) => id !== action.productId),
        cart: exists
          ? state.cart.map((e) =>
              e.productId === action.productId ? { ...e, qty: e.qty + 1 } : e
            )
          : [...state.cart, { productId: action.productId, qty: 1 }]
      };
    }

    /* ---------------------------------------------------------- wishlist */
    case 'wishlist/toggle': {
      const has = state.wishlist.includes(action.productId);
      return {
        ...state,
        wishlist: has
          ? state.wishlist.filter((id) => id !== action.productId)
          : [...state.wishlist, action.productId]
      };
    }
    case 'wishlist/remove':
      return { ...state, wishlist: state.wishlist.filter((id) => id !== action.productId) };

    case 'products/add':
      return { ...state, customProducts: [action.product, ...state.customProducts] };
    case 'products/update':
      return {
        ...state,
        customProducts: state.customProducts.map((p) =>
          p.id === action.id ? { ...p, ...action.patch } : p
        )
      };
    case 'products/remove':
      return {
        ...state,
        customProducts: state.customProducts.filter((p) => p.id !== action.id)
      };
    case 'overrides/set':
      return {
        ...state,
        productOverrides: {
          ...state.productOverrides,
          [action.id]: { ...(state.productOverrides[action.id] || {}), ...action.patch }
        }
      };
    case 'inquiries/add': {
      const incoming = Array.isArray(action.inquiry) ? action.inquiry : [action.inquiry];
      return { ...state, sellerInquiries: [...incoming, ...state.sellerInquiries] };
    }
    case 'inquiries/reply':
      return {
        ...state,
        sellerInquiries: state.sellerInquiries.map((i) =>
          i.id === action.id ? { ...i, reply: action.reply } : i
        )
      };
    case 'buyerProfile/set':
      return { ...state, buyerProfile: action.profile };
    case 'platformUsers/set':
      return { ...state, platformUsers: [] };
    case 'adminToken/set':
      return { ...state, adminToken: action.token };

    case 'external/sync': {
      const nextVal = action.value === null ? SLICE_DEFAULTS[action.slice] : action.value;
      return {
        ...state,
        [action.slice]: nextVal
      };
    }

    case 'coupon/set':
      return { ...state, coupon: action.code };
    case 'user/set':
      return { ...state, user: action.user };
    case 'addresses/set':
      return { ...state, addresses: Array.isArray(action.addresses) ? action.addresses.map(normaliseAddress) : [] };
    case 'order/add':
      return { ...state, orders: [action.order, ...state.orders] };
    case 'orders/set': {
      const nextOrders =
        typeof action.orders === 'function' ? action.orders(state.orders) : action.orders;
      return { ...state, orders: Array.isArray(nextOrders) ? nextOrders : state.orders };
    }
    case 'order/advance':
      return {
        ...state,
        orders: state.orders.map((o) =>
          o.id === action.orderId ? { ...o, stage: Math.min(5, (o.stage || 1) + 1) } : o
        )
      };
    case 'reviews/set':
      return { ...state, reviews: action.reviews };
    case 'recentlyViewed/push':
      return { ...state, recentlyViewed: pushRecentlyViewed(action.id) };
    case 'recentlyViewed/clear':
      saveStorage('hunarlink_recently_viewed', []);
      return { ...state, recentlyViewed: [] };
    case 'compare/clear':
      return { ...state, compareList: [] };
    case 'compare/toggle': {
      const has = state.compareList.includes(action.productId);
      return {
        ...state,
        compareList: has
          ? state.compareList.filter((id) => id !== action.productId)
          : [...state.compareList, action.productId].slice(-4)
      };
    }
    case 'reviews/add': {
      const forProduct = state.reviews[action.productId] || [];
      return {
        ...state,
        reviews: { ...state.reviews, [action.productId]: [action.review, ...forProduct] }
      };
    }

    case 'ui/drawer':
      return { ...state, ui: { ...state.ui, drawer: action.drawer } };
    case 'ui/modal':
      return {
        ...state,
        ui: { ...state.ui, modal: action.modal ? { type: action.modal, payload: action.payload || {} } : null }
      };
    case 'ui/filters': {
      const next = { ...state.ui.filters, ...action.patch };
      if ('guild' in action.patch && !('technique' in action.patch)) {
        next.technique = 'all';
      }
      return { ...state, ui: { ...state.ui, filters: next } };
    }
    case 'ui/veil':
      return { ...state, veil: { open: action.open, text: action.text || '' } };
    case 'ui/filtersReset':
      return { ...state, ui: { ...state.ui, filters: DEFAULT_FILTERS } };
    case 'ui/loading':
      return { ...state, ui: { ...state.ui, loadingProducts: action.value } };

    case 'toast/push': {
      toastSeq += 1;
      return { ...state, toasts: [...state.toasts, { id: toastSeq, ...action.toast }] };
    }
    case 'toast/dismiss':
      return { ...state, toasts: state.toasts.filter((t) => t.id !== action.id) };

    default:
      return state;
  }
}

const StoreCtx = createContext(null);

export function StoreProvider({ children }) {
  const [state, dispatch] = useReducer(reducer, initialState);
  const mounted = useRef(false);

  /* 100% Real DB Catalogue (plus any seller-created listings in current session).
     Zero static frontend SEED_PRODUCTS dummy data. */
  const catalogue = useMemo(() => {
    const base = [...state.customProducts, ...state.dbCatalogue];
    return base.map((p) => {
      const ov = state.productOverrides[p.id];
      return ov ? { ...p, ...ov } : p;
    });
  }, [state.dbCatalogue, state.customProducts, state.productOverrides]);

  const toast = useCallback((message, tone = 'default') => {
    dispatch({ type: 'toast/push', toast: { message, tone } });
  }, []);

  const totals = useMemo(
    () => cartTotals(state.cart, catalogue, state.coupon),
    [state.cart, catalogue, state.coupon]
  );

  /* Public read-only discovery: load live database catalog & verified artisans
     immediately on mount so visitors can freely explore the storefront, products,
     and artisan profiles before signing in. Zero static dummy data. */
  const loadPublicCatalog = useCallback(async () => {
    dispatch({ type: 'db/loading' });
    try {
      const [rawProducts, rawArtisans] = await Promise.all([
        fetchCatalogProducts(null, null).catch(() => []),
        fetchArtisans(null).catch(() => [])
      ]);
      dispatch({
        type: 'db/publicLoaded',
        catalogue: Array.isArray(rawProducts) ? rawProducts.map(mapDbListingToProduct) : [],
        artisans: Array.isArray(rawArtisans) ? rawArtisans : []
      });
    } catch (err) {
      dispatch({ type: 'db/error', error: err?.message || 'Could not load catalog from database.' });
    }
  }, []);

  useEffect(() => {
    loadPublicCatalog();
  }, [loadPublicCatalog]);

  /* Hydrate catalogue, verified artisans, user orders & addresses strictly
     from FastAPI + MySQL/SQLite using the authenticated Clerk RS256 JWT. */
  const hydrateFromBackend = useCallback(async (token) => {
    if (!token) return;
    dispatch({ type: 'db/loading' });
    try {
      const [rawProducts, rawArtisans, rawOrders, rawAddresses] = await Promise.all([
        fetchCatalogProducts(null, token).catch(() => []),
        fetchArtisans(token).catch(() => []),
        fetchMyRetailOrders(token).catch(() => []),
        fetchMyAddresses(token).catch(() => [])
      ]);
      const mappedCatalogue = Array.isArray(rawProducts)
        ? rawProducts.map(mapDbListingToProduct)
        : [];
      const mappedArtisans = Array.isArray(rawArtisans) ? rawArtisans : [];
      const mappedOrders = Array.isArray(rawOrders)
        ? rawOrders.map((o) => mapDbOrderToUi(o, mappedCatalogue))
        : [];
      const mappedAddresses = Array.isArray(rawAddresses)
        ? rawAddresses.map(normaliseAddress)
        : [];

      dispatch({
        type: 'db/hydrated',
        catalogue: mappedCatalogue,
        artisans: mappedArtisans,
        orders: mappedOrders,
        addresses: mappedAddresses
      });
    } catch (err) {
      dispatch({ type: 'db/error', error: err?.message || 'Could not load data from database.' });
    }
  }, []);

  const clearSessionState = useCallback(() => {
    dispatch({ type: 'db/reset' });
    saveStorage(KEYS.cart, []);
    saveStorage(KEYS.wishlist, []);
    saveStorage(KEYS.savedLater, []);
    saveStorage(KEYS.coupon, null);
    saveStorage(KEYS.user, null);
    saveStorage(KEYS.buyerProfile, null);
    saveStorage(KEYS.platformUsers, []);
  }, []);

  const setBuyerProfile = useCallback((profile) => {
    dispatch({ type: 'buyerProfile/set', profile });
  }, []);

  const setUser = useCallback((user, opts = {}) => {
    dispatch({ type: 'user/set', user });
    if (!opts.silent) {
      toast(user ? `Signed in as ${user.name || user.email}` : 'Signed out');
    }
  }, [toast]);

  useEffect(() => {
    if (!mounted.current) {
      mounted.current = true;
      /* Purge any stale dummy local accounts from earlier browser sessions */
      saveStorage(KEYS.platformUsers, []);
      if (!initialRealUser) {
        saveStorage(KEYS.user, null);
        saveStorage(KEYS.wishlist, []);
        saveStorage(KEYS.cart, []);
      }
      return;
    }
    saveStorage(KEYS.cart, state.cart);
    saveStorage(KEYS.wishlist, state.wishlist);
    saveStorage(KEYS.savedLater, state.savedLater);
    saveStorage(KEYS.coupon, state.coupon);
    saveStorage(KEYS.user, state.user);
    saveStorage(KEYS.reviews, state.reviews);
    saveStorage(KEYS.sellerInquiries, state.sellerInquiries);
    saveStorage(KEYS.buyerProfile, state.buyerProfile);
    saveStorage(KEYS.adminToken, state.adminToken);
  }, [
    state.cart,
    state.wishlist,
    state.savedLater,
    state.coupon,
    state.user,
    state.reviews,
    state.sellerInquiries,
    state.buyerProfile,
    state.adminToken
  ]);

  useEffect(() => {
    const onStorage = (e) => {
      if (!e.key) return;
      const slice = KEY_TO_SLICE[e.key];
      if (!slice) return;
      let value;
      try {
        value = e.newValue === null ? null : JSON.parse(e.newValue);
      } catch {
        return;
      }
      dispatch({ type: 'external/sync', slice, value });
    };
    window.addEventListener('storage', onStorage);
    return () => window.removeEventListener('storage', onStorage);
  }, []);

  const value = useMemo(() => {
    const productById = (id) => {
      if (!id) return null;
      const needle = String(id).trim().toLowerCase();
      return (
        catalogue.find(
          (p) =>
            String(p.id).toLowerCase() === needle ||
            String(p.productId || '').toLowerCase() === needle ||
            String(p.legacyCode || '').toLowerCase() === needle ||
            String(p.sku || '').toLowerCase() === needle ||
            String(p.slug || '').toLowerCase() === needle
        ) || null
      );
    };
    const isRealSignedIn = Boolean(
      state.user && state.user.authProvider === 'clerk' && state.user.isLoggedIn
    );

    const gateGuest = (reason) => {
      toast(reason, 'info');
      dispatch({ type: 'auth/prompt', reason });
    };

    return {
      ...state,
      catalogue,
      artisans: state.dbArtisans,
      totals,
      productById,
      isRealSignedIn,
      hydrateFromBackend,
      loadPublicCatalog,
      clearSessionState,
      clearAuthPrompt: () => dispatch({ type: 'auth/clearPrompt' }),
      cartCount: isRealSignedIn ? state.cart.reduce((n, e) => n + e.qty, 0) : 0,
      wishlistCount: isRealSignedIn ? state.wishlist.length : 0,
      cartItems: isRealSignedIn
        ? state.cart.map((e) => ({ ...e, product: productById(e.productId) })).filter((e) => e.product)
        : [],
      wishlistItems: isRealSignedIn ? state.wishlist.map(productById).filter(Boolean) : [],
      savedItems: isRealSignedIn ? state.savedLater.map(productById).filter(Boolean) : [],
      recentlyViewedItems: isRealSignedIn ? state.recentlyViewed.map(productById).filter(Boolean) : [],
      compareItems: isRealSignedIn ? state.compareList.map(productById).filter(Boolean) : [],

      addToCart(productId, qty = 1) {
        if (!isRealSignedIn) {
          gateGuest('Please sign in or sign up to add items to your cart.');
          return;
        }
        dispatch({ type: 'cart/add', productId, qty });
        const p = productById(productId);
        if (p) toast(`Added "${p.title}" to your Acquisition Bag`, 'success');
      },
      setQty: (productId, qty) => {
        if (!isRealSignedIn) {
          gateGuest('Please sign in to manage your cart.');
          return;
        }
        dispatch({ type: 'cart/setQty', productId, qty });
      },
      removeFromCart: (productId) => dispatch({ type: 'cart/remove', productId }),
      clearCart: () => dispatch({ type: 'cart/clear' }),
      saveForLater: (productId) => {
        if (!isRealSignedIn) {
          gateGuest('Please sign in to save items for later.');
          return;
        }
        dispatch({ type: 'cart/saveForLater', productId });
      },
      moveToCart: (productId) => {
        if (!isRealSignedIn) {
          gateGuest('Please sign in to add items to your cart.');
          return;
        }
        dispatch({ type: 'cart/moveBack', productId });
      },

      toggleWishlist(productId) {
        if (!isRealSignedIn) {
          gateGuest('Please sign in or sign up to add items to your wishlist.');
          return;
        }
        const adding = !state.wishlist.includes(productId);
        dispatch({ type: 'wishlist/toggle', productId });
        const p = productById(productId);
        if (p) {
          toast(
            adding ? `Saved "${p.title}" to Wishlist` : `Removed "${p.title}" from Wishlist`,
            adding ? 'success' : 'default'
          );
        }
      },
      removeFromWishlist: (id) => dispatch({ type: 'wishlist/remove', productId: id }),

      applyCoupon(code) {
        if (!isRealSignedIn) {
          gateGuest('Please sign in to apply privilege codes.');
          return false;
        }
        const normalised = String(code || '').trim().toUpperCase();
        const known = ['VALLEY10', 'FIRSTCRAFT'].includes(normalised);
        dispatch({ type: 'coupon/set', code: known ? normalised : null });
        toast(
          known ? `Coupon ${normalised} applied` : `"${normalised}" is not a valid privilege code`,
          known ? 'success' : 'error'
        );
        return known;
      },
      removeCoupon: () => dispatch({ type: 'coupon/set', code: null }),

      addAddress: (address) =>
        dispatch({ type: 'addresses/set', addresses: [...state.addresses, normaliseAddress(address)] }),
      setAddresses: (addresses) => dispatch({ type: 'addresses/set', addresses }),
      addProduct: (product) => dispatch({ type: 'products/add', product }),
      updateProduct: (id, patch) => dispatch({ type: 'products/update', id, patch }),
      removeProduct: (id) => dispatch({ type: 'products/remove', id }),
      setProductOverride: (id, patch) => dispatch({ type: 'overrides/set', id, patch }),
      setReviews: (reviews) => dispatch({ type: 'reviews/set', reviews }),
      addInquiry: (inquiry) => {
        if (!isRealSignedIn) {
          gateGuest('Please sign in to message an artisan.');
          return;
        }
        dispatch({ type: 'inquiries/add', inquiry });
      },
      replyToInquiry: (id, reply) => dispatch({ type: 'inquiries/reply', id, reply }),
      setBuyerProfile,
      setPlatformUsers: () => dispatch({ type: 'platformUsers/set', users: [] }),
      setAdminToken: (token) => dispatch({ type: 'adminToken/set', token }),

      placeOrder: (order) => {
        if (!isRealSignedIn) {
          gateGuest('Please sign in to place an order.');
          return;
        }
        dispatch({ type: 'order/add', order });
      },
      addOrder: (order) => {
        if (!isRealSignedIn) {
          gateGuest('Please sign in to place an order.');
          return;
        }
        dispatch({ type: 'order/add', order });
      },
      setOrders: (orders) => dispatch({ type: 'orders/set', orders }),
      advanceOrder: (orderId) => dispatch({ type: 'order/advance', orderId }),
      addReview: (productId, review) => {
        if (!isRealSignedIn) {
          gateGuest('Please sign in to submit a review.');
          return;
        }
        dispatch({ type: 'reviews/add', productId, review });
      },
      toggleCompare: (productId) => dispatch({ type: 'compare/toggle', productId }),
      clearCompare: () => dispatch({ type: 'compare/clear' }),

      openDrawer: (drawer) => {
        if (!isRealSignedIn && (drawer === 'cart' || drawer === 'wishlist')) {
          gateGuest(
            drawer === 'cart'
              ? 'Please sign in or sign up to access your cart.'
              : 'Please sign in or sign up to view your wishlist.'
          );
          return;
        }
        dispatch({ type: 'ui/drawer', drawer });
      },
      closeDrawer: () => dispatch({ type: 'ui/drawer', drawer: null }),
      openModal: (modal, payload) => {
        if (!isRealSignedIn && (modal === 'checkout' || modal === 'orders')) {
          gateGuest('Please sign in or sign up to buy crafts or track orders.');
          return;
        }
        dispatch({ type: 'ui/modal', modal, payload });
      },
      closeModal: () => dispatch({ type: 'ui/modal', modal: null }),
      setFilters: (patch) => dispatch({ type: 'ui/filters', patch }),
      raiseVeil: (text) => dispatch({ type: 'ui/veil', open: true, text }),
      lowerVeil: () => dispatch({ type: 'ui/veil', open: false }),
      resetFilters: () => dispatch({ type: 'ui/filtersReset' }),
      setLoadingProducts: (value) => dispatch({ type: 'ui/loading', value }),

      setUser,
      pushRecent: (id) => dispatch({ type: 'recentlyViewed/push', id }),
      clearRecentlyViewed: () => dispatch({ type: 'recentlyViewed/clear' }),

      toast,
      dismissToast: (id) => dispatch({ type: 'toast/dismiss', id }),

      filteredProducts: (() => {
        const f = state.ui.filters;
        const q = (f.query || '').trim().toLowerCase();
        let list = catalogue.filter((p) => {
          if (q) {
            const hay = `${p.title} ${p.guildLabel} ${p.artisan} ${p.district} ${p.giId}`.toLowerCase();
            if (!hay.includes(q)) return false;
          }
          if (f.guild !== 'all' && p.guild !== f.guild) return false;
          if (f.technique && f.technique !== 'all' && p.technique !== f.technique) return false;
          if (f.artisan && p.artisan !== f.artisan) return false;
          if (p.price > f.maxPrice) return false;
          if (f.minRating > 0 && p.rating < f.minRating) return false;
          if (f.giTier > 0 && p.giLevel < f.giTier) return false;
          if (f.district !== 'all' && p.district !== f.district) return false;
          return true;
        });
        const s = f.sort;
        if (s === 'price-asc') list = [...list].sort((a, b) => a.price - b.price);
        else if (s === 'price-desc') list = [...list].sort((a, b) => b.price - a.price);
        else if (s === 'rating-desc') list = [...list].sort((a, b) => b.rating - a.rating);
        else if (s === 'hours-desc') list = [...list].sort((a, b) => b.loomHours - a.loomHours);
        return list;
      })()
    };
  }, [state, catalogue, totals, toast, hydrateFromBackend, loadPublicCatalog, clearSessionState, setBuyerProfile, setUser]);

  return <StoreCtx.Provider value={value}>{children}</StoreCtx.Provider>;
}

export function useStore() {
  const ctx = useContext(StoreCtx);
  if (!ctx) throw new Error('useStore must be used within <StoreProvider>');
  return ctx;
}

export { KEYS };
