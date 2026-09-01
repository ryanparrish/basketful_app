# Participant Frontend - Build Overview

_Last updated: 2026-07-13_

## Summary

The participant-facing frontend is a mobile-friendly web app for program participants to browse products, manage their shopping cart, and place orders. It is built on **Refine** (`@refinedev/core` + `@refinedev/mui`) for routing/resource/auth wiring, Material-UI for components, TanStack Query for data fetching, and i18next for English/Spanish translation. Authentication uses httpOnly cookie-based JWTs (not tokens in local storage).

## What Was Built

### Core Infrastructure

- **Providers** (`src/providers/`)
  - `QueryProvider` - TanStack Query with mobile-optimized caching
  - `AuthProvider` (`AuthContext.tsx`) - Cookie-based auth state (user profile in `localStorage`, tokens in httpOnly cookies), applies the participant's saved language preference on login
  - `CartProvider` - Shopping cart state with `react-use-cart`
  - `ValidationProvider` - Real-time backend cart validation with debouncing
  - `src/providers/refine/` - Refine's own `authProvider`, `dataProvider`, and `i18nProvider`, used by the `<Refine>` component in `App.tsx` for route protection, resource labels, and identity (`useGetIdentity`, `useLogout`, `useGo`, etc.)

- **i18n** (`src/i18n/`, `src/locales/`)
  - i18next + react-i18next + `i18next-browser-languagedetector`
  - English (`locales/en.json`) and Spanish (`locales/es.json`) bundled statically (both ship in the JS bundle so translations work offline)
  - Language precedence at startup: `localStorage` → browser language → English; after login, the participant's saved backend preference (`user.preferred_language`) wins
  - `LanguageSwitcher` component (menu variant used in the header) and `useLanguagePreference` hook persist a language change back to the backend via `PATCH /participants/me/profile/`

- **Theme System** (`src/shared/theme/`)
  - `dynamicTheme.ts` - Fetches theme config from `/settings/theme-config/` via TanStack Query, cached with `staleTime`/`refetchInterval` of 4 hours
  - `tokens.ts` - Brand color/spacing tokens consumed by `dynamicTheme.ts` (primary/secondary colors are always forced to brand green/orange regardless of backend override; only logo, app name, and favicon come from the backend)
  - Material-UI theming with 44px minimum touch targets

- **API Layer** (`src/shared/api/`)
  - `secureClient.ts` - Axios client using httpOnly cookies (`withCredentials: true`), CSRF token attached from the `csrftoken` cookie on mutations, automatic `/auth/refresh/` retry on 401 with request queuing, dispatches a `session-expired` window event on refresh failure (caught by `SessionExpiredDialog`)
  - `endpoints.ts` - Typed API functions for all backend calls
  - `types/api.ts` - TypeScript interfaces

### Features (Complete)

#### Authentication (`/features/auth`)
- `LoginPage` - Customer number and password login, with Google reCAPTCHA (`react-google-recaptcha`)
- Cookie-based session (server sets httpOnly JWT cookies); client only caches the user profile
- Route protection via Refine's `<Authenticated>` wrapper + `authProvider.check()`, redirecting to `/login` (with `?session_expired=true` on token expiry)

#### Products (`/features/products`)
- `ProductsPage` - Main shopping interface with search
- `ProductGrid` - Responsive grid (2 cols at `xs`, 3 at `sm`, 4 at `md`/`lg`)
- `ProductCard` - Individual product display with add-to-cart
- `CategoryTabs` - Horizontal scrollable category filter with counts (mobile); on desktop, category navigation instead lives in `CustomSider`
- Real-time validation feedback on product cards

#### Shopping Cart (`/features/cart`)
- `CartDrawer` - Slide-out drawer with cart contents, opened from the header cart icon
- `CartItem` - Individual cart item with quantity controls (uses `react-swipeable-list` for swipe-to-remove)
- `ValidationFeedback` - Displays validation errors and warnings
- Real-time backend validation with 500ms debounce
- Budget remaining display (also shown in the desktop sidebar banner)

#### Orders (`/features/orders`)
- `CheckoutPage` - Review cart and place order
- `OrderHistory` - View past orders
- `OrderCard` - Expandable order details

### Shared Components (`/components`)
- `components/refine/CustomHeader` - Fixed top app bar: branding/logo, language switcher, cart icon (desktop), user avatar menu (Account/Logout) — replaces the old `AppHeader`
- `components/refine/CustomSider` - Collapsible desktop-only left nav (Shop/Orders/Account + category list with item counts and a budget-remaining banner); hidden on mobile (`ThemedLayout`'s `Sider` slot)
- `OfflineBanner` - Slide-down banner shown when offline / reconnected
- `SessionExpiredDialog` - Listens for the `session-expired` event and prompts re-login
- `LanguageSwitcher` - Menu-based language toggle (English/Spanish)
- `AccountPage` - User profile, balances, and a shortcut to order history

> Note: there is no dedicated mobile bottom-navigation component. On small screens, `CustomSider` is hidden and navigation happens via the header's account menu and in-page links (e.g. `AccountPage` → "View Orders"). A stale comment in `CustomSider.tsx` references a bottom nav that does not exist in the codebase.

### Shared Hooks (`/shared/hooks`)
- `useVisibilityPolling` - Polls only when page visible
- `useRuleVersion` - Monitors rule changes and triggers revalidation
- `useOrderWindow` - Checks if ordering is open/closed
- `useCartValidation` - Easy cart validation access (also exposes `remainingBudget`/`isOverBudget` used by the sidebar)
- `useNetworkStatus` - Online/offline detection, used by `OfflineBanner`
- `useFormatters` - Locale-aware currency/number formatting
- `useLanguagePreference` - Syncs the active i18next language with the backend-saved preference

## Technology Stack

```json
{
  "framework": "React 19.2 + TypeScript 5.9",
  "build": "Vite 7.3",
  "app-framework": "Refine 5 (@refinedev/core, @refinedev/mui, @refinedev/react-router)",
  "ui": "Material-UI 7.3",
  "state": "TanStack Query 5.90 + react-use-cart",
  "routing": "React Router 7.13 (via @refinedev/react-router)",
  "http": "Axios 1.16 (httpOnly cookie auth)",
  "i18n": "i18next 26 + react-i18next 17",
  "testing": "Vitest 4 + React Testing Library"
}
```

`vite-plugin-pwa` and `workbox-window` are present in `package.json` but **are not wired into `vite.config.ts`** — no service worker / PWA manifest is currently generated by the build. Offline handling today is limited to `OfflineBanner` (network status detection) and TanStack Query's cache; there is no installable PWA or offline asset caching yet.

## File Structure

```
participant-frontend/
├── src/
│   ├── App.tsx                        # Refine setup, routing, layout composition
│   ├── main.tsx                        # Entry point
│   ├── components/
│   │   ├── AccountPage.tsx
│   │   ├── OfflineBanner.tsx
│   │   ├── SessionExpiredDialog.tsx
│   │   ├── LanguageSwitcher.tsx
│   │   ├── index.ts
│   │   └── refine/
│   │       ├── CustomHeader.tsx
│   │       ├── CustomSider.tsx
│   │       └── index.ts
│   ├── features/
│   │   ├── auth/
│   │   │   ├── LoginPage.tsx
│   │   │   └── index.ts
│   │   ├── products/
│   │   │   ├── ProductsPage.tsx
│   │   │   ├── ProductGrid.tsx
│   │   │   ├── ProductCard.tsx
│   │   │   ├── CategoryTabs.tsx
│   │   │   └── index.ts
│   │   ├── cart/
│   │   │   ├── CartDrawer.tsx
│   │   │   ├── CartItem.tsx
│   │   │   ├── ValidationFeedback.tsx
│   │   │   └── index.ts
│   │   └── orders/
│   │       ├── CheckoutPage.tsx
│   │       ├── OrderHistory.tsx
│   │       ├── OrderCard.tsx
│   │       ├── __tests__/OrderHistory.test.tsx
│   │       └── index.ts
│   ├── i18n/
│   │   ├── index.ts                    # i18next init
│   │   ├── languages.ts                # Supported language registry
│   │   └── i18next.d.ts
│   ├── locales/
│   │   ├── en.json
│   │   └── es.json
│   ├── providers/
│   │   ├── AuthContext.tsx
│   │   ├── CartProvider.tsx
│   │   ├── QueryProvider.tsx
│   │   ├── ValidationContext.tsx
│   │   ├── index.ts
│   │   └── refine/
│   │       ├── authProvider.ts
│   │       ├── dataProvider.ts
│   │       ├── i18nProvider.ts
│   │       └── index.ts
│   ├── shared/
│   │   ├── api/
│   │   │   ├── secureClient.ts         # Axios + httpOnly cookie auth
│   │   │   ├── endpoints.ts            # API functions
│   │   │   └── __tests__/endpoints.test.ts
│   │   ├── constants/
│   │   │   └── layout.ts               # Centralized layout/spacing constants
│   │   ├── types/
│   │   │   └── api.ts
│   │   ├── theme/
│   │   │   ├── dynamicTheme.ts
│   │   │   └── tokens.ts
│   │   ├── utils/
│   │   │   └── formatters.ts
│   │   └── hooks/
│   │       ├── useVisibilityPolling.ts
│   │       ├── useRuleVersion.ts
│   │       ├── useOrderWindow.ts
│   │       ├── useCartValidation.ts
│   │       ├── useNetworkStatus.ts
│   │       ├── useFormatters.ts
│   │       ├── useLanguagePreference.ts
│   │       └── index.ts
│   └── test/
│       └── setup.ts                    # Vitest/RTL setup
├── nginx.conf                          # Serves the built app under /new/cart/
├── Dockerfile                          # node:20-alpine build → nginx:1.27-alpine
├── package.json
├── vite.config.ts
├── vitest.config.ts
└── tsconfig*.json
```

## Key Features Implemented

### 1. Backend Cart Validation
- Automatic validation on cart changes (500ms debounce)
- Real-time error/warning display on product cards
- Budget checking with grace allowance support
- Quantity limit enforcement
- Rule version tracking with auto-revalidation

### 2. Refine-Driven Routing & Layout
- `@refinedev/core` resources (`products`, `checkout`, `orders`, `account`) drive nav labels and route protection
- `Authenticated` wrapper redirects unauthenticated users to `/login`, preserving deep links
- Desktop layout: fixed `CustomHeader` + collapsible `CustomSider`; mobile: header only, no sidebar

### 3. Internationalization
- English and Spanish, both bundled (no lazy-loading of locale bundles)
- Backend-synced preference so order confirmation emails / API responses match the participant's saved language

### 4. Mobile-First Design
- Touch-friendly targets (44px minimum, enforced via MUI theme overrides)
- Responsive grid (2-4 columns based on screen size)
- Swipeable cart items (`react-swipeable-list`)

### 5. Offline Detection (not full PWA)
- `useNetworkStatus` + `OfflineBanner` detect and surface connectivity loss/recovery
- TanStack Query caching reduces API calls while online
- No service worker is currently built (see PWA note above)

### 6. Security
- httpOnly cookie JWTs (mitigates XSS token theft)
- CSRF token header on mutating requests
- Automatic refresh-and-retry on 401, with a `session-expired` event for UI handling
- Google reCAPTCHA on login

## Environment Configuration

Create a `.env` (or `.env.local`) file:
```env
VITE_API_URL=http://localhost:8000/api/v1
VITE_BASE_PATH=/new/cart/
```

`VITE_BASE_PATH` sets Vite's `base` for production builds (default `/new/cart/` if unset) — the app is deployed under a subpath, not at the domain root. `VITE_API_URL` is also used as the dev-server proxy target for `/api`.

## Running the App

### Development
```bash
cd participant-frontend
npm install
npm run dev
```

### Tests
```bash
npm run test        # vitest run
npm run test:watch  # vitest watch mode
```
Vitest + `@testing-library/react` + `jsdom` are configured (`vitest.config.ts`, `src/test/setup.ts`). Existing test suites cover `OrderHistory` and the API `endpoints` module.

### Production Build
```bash
npm run build     # tsc -b && vite build
npm run preview
```

### Docker (standalone image)
```bash
docker build -t basketful-participant ./participant-frontend
docker run -p 8082:80 basketful-participant
```
The `Dockerfile` builds with Node 20 (`npm ci` + `vite build`, accepting `VITE_API_URL`/`VITE_BASE_PATH` build args) and serves the static output from `nginx:1.27-alpine`.

### Docker (via docker-compose)
```bash
# From the repo root
docker compose -f docker-compose.frontend-participant.yml up
```
`docker-compose.frontend-participant.yml` pulls the published image (`${DOCKER_USERNAME}/basketful-participant:${FRONTEND_IMAGE_TAG:-latest}`), exposes it on host port `${PARTICIPANT_FRONTEND_PORT:-8082}` (container port 80), and health-checks `GET /healthz`.

## Serving / Nginx

`participant-frontend/nginx.conf` serves the SPA under the `/new/cart/` path (matching the Vite `base`):
```nginx
location = /healthz {
    return 200 "ok\n";
}
location /new/cart/ {
    alias /usr/share/nginx/html/;
    try_files $uri $uri/ /new/cart/index.html;
}
```
Anything outside `/new/cart/` (including the bare domain root) is not routed by this config — the participant app is expected to sit behind a reverse proxy / gateway that forwards that path prefix.

## API Endpoints Used

**Public (No Auth)**
- `GET /settings/theme-config/` - Theme and branding
- `GET /settings/program-config/` - Program rules
- `GET /settings/order-window-status/` - Global order window status
- `POST /auth/login/` - Customer login (customer number + password + reCAPTCHA token)

**Authenticated**
- `GET /auth/me/` - Session/auth check
- `POST /auth/refresh/` - Refresh JWT (cookie-based, no body)
- `POST /auth/logout/` - Logout (blacklists tokens server-side)
- `GET /products/` - Product list (`page_size=500`, `active=true`)
- `GET /categories/` - Categories
- `GET /rules/version/` - Rule version for revalidation triggers
- `GET /settings/my-window/` - Per-participant order window status
- `GET /participants/me/profile/` / `PATCH /participants/me/profile/` - Profile + language preference
- `GET /participants/me/balances/` - Available/hygiene/go-fresh/full balances
- `GET /account-balances/me/` - Legacy balances endpoint (still called by `getAccountBalance`)
- `POST /orders/validate-cart/` - Cart validation
- `POST /orders/` - Create order
- `GET /orders/` - Order history (`me=true`)
- `GET /orders/{id}/` - Order detail
- `POST /orders/{id}/confirm/` - Confirm order

## Testing

- **Automated**: Vitest + React Testing Library, run via `npm run test`. Coverage is limited (one feature test, one API-layer test) — most components/hooks are untested.
- **Manual Testing Checklist**
  - [ ] Login with customer number (and reCAPTCHA)
  - [ ] Browse products by category (mobile tabs vs. desktop sidebar)
  - [ ] Search products
  - [ ] Add items to cart, verify swipe-to-remove
  - [ ] Validate cart (trigger budget/limit errors)
  - [ ] Place order
  - [ ] View order history
  - [ ] Test offline banner (disable network)
  - [ ] Test cart persistence on refresh
  - [ ] Test session-expired flow (cookie/refresh failure)
  - [ ] Switch language and confirm it persists after logout/login
  - [ ] Test on mobile device (no sidebar, no bottom nav)

## Known Limitations

1. **No PWA / service worker despite the dependency** - `vite-plugin-pwa` is installed but not configured in `vite.config.ts`; there's no offline asset caching or "Add to Home Screen" support yet.
2. **No dedicated mobile navigation component** - mobile users rely on the header's account menu and in-page links; `CustomSider.tsx` has a stale comment implying a bottom nav that doesn't exist.
3. **Thin automated test coverage** - only `OrderHistory` and `endpoints` have tests; most features/hooks/providers are untested.
4. **No global error boundary** - no React error boundary component exists; an uncaught render error will blank the app.
5. **No analytics** - no tracking/monitoring is wired up.
6. **Bundle size not tracked** - no current bundle-size budget or code-splitting by route; everything loads in the initial bundle.

## Next Steps (Optional Enhancements)

1. Wire up `vite-plugin-pwa` (or remove the unused dependency) and decide on an offline-caching strategy
2. Add a mobile bottom navigation (or otherwise resolve the stale `CustomSider` comment)
3. Expand automated test coverage (cart, validation, auth flows)
4. Add a React Error Boundary
5. Route-based code splitting (`React.lazy`)
6. Accessibility audit (ARIA labels, keyboard nav, screen reader, contrast)

## Support & Documentation

- React: https://react.dev
- Refine: https://refine.dev
- Material-UI: https://mui.com
- TanStack Query: https://tanstack.com/query
- Vite: https://vitejs.dev
- i18next: https://www.i18next.com
