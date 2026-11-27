import { useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { useStore } from '../state/StoreContext.jsx';

/* ==========================================================================
   usePageTitle
   --------------------------------------------------------------------------
   Every route used to inherit the single <title> from index.html, so a browser
   tab strip showed "HunarLink — GI-Certified Kashmiri Handicrafts Marketplace"
   seven times over and history entries were indistinguishable. ProductPage
   already set its own; this gives the rest the same treatment.

   Pages that need a dynamic title (a product name, a seller's store name) can
   still call document.title directly after mount — this hook only sets the
   route-level fallback, and it re-runs on every navigation.
   ========================================================================== */

const SUFFIX = 'HunarLink — Valley Craft Guild';

const TITLES = {
  '/': 'Storefront',
  '/index.html': 'Storefront',
  '/product': 'Product',
  '/product.html': 'Product',
  '/artisan': 'Artisan Workshop',
  '/artisan.html': 'Artisan Workshop',
  '/artisans': 'Our Artisans',
  '/auth': 'Artisan Sign In & Verification',
  '/auth.html': 'Artisan Sign In & Verification',
  '/wholesale': 'Wholesale Desk',
  '/wholesale.html': 'Wholesale Desk',
  '/admin': 'Admin Console',
  '/admin.html': 'Admin Console',
  '/seller': 'Artisan Portal',
  '/seller.html': 'Artisan Portal',
  '/login': 'User Sign In',
  '/login.html': 'User Sign In',
  '/register': 'Create HunarLink Account',
  '/register.html': 'Create HunarLink Account',
  '/orders': 'My Orders',
  '/orders.html': 'My Orders',
  '/profile': 'My Profile',
  '/profile.html': 'My Profile'
};

export default function usePageTitle() {
  const { pathname } = useLocation();
  const { adminToken } = useStore();

  useEffect(() => {
    const isAdminRoute = pathname === '/admin' || pathname === '/admin.html';
    let label = isAdminRoute && !adminToken ? 'Admin Login' : TITLES[pathname];
    if (!label && pathname.startsWith('/artisans/')) {
      const slug = decodeURIComponent(pathname.slice('/artisans/'.length)).replace(/\/+$/, '');
      if (slug) {
        label = slug
          .split('-')
          .filter(Boolean)
          .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
          .join(' ');
      }
    }
    /* '/' is the storefront, so it takes the brand title alone */
    if (!label || pathname === '/' || pathname === '/index.html') {
      document.title = SUFFIX;
      return;
    }
    document.title = `${label} · ${SUFFIX}`;
  }, [pathname, adminToken]);
}
