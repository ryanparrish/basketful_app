# Cookie-Based Authentication Migration - Remaining Cleanup

## ✅ Completed
1. **Axios & reCAPTCHA installed** - Dependencies added to package.json
2. **API Client created** - `/frontend/src/lib/api/apiClient.ts` with CSRF handling and automatic token refresh
3. **Session expiry notifications** - Error notifications display when session expires
4. **reCAPTCHA on login** - `/frontend/src/pages/Login.tsx` with Google reCAPTCHA v2
5. **AuthProvider migrated** - `/frontend/src/providers/authProvider.ts` uses `/auth/login/` endpoint with cookies
6. **DataProvider migrated** - `/frontend/src/providers/dataProvider.ts` uses apiClient instead of fetchUtils

## 🔄 Partial - localStorage Token Cleanup

The following files still have `localStorage.getItem('accessToken')` calls that need to be replaced with `apiClient` calls:

### Files Already Fixed
- ✅ `/frontend/src/pages/BulkVoucherCreate.tsx` - Fixed wrong key ('token' → apiClient)
- ✅ `/frontend/src/pages/Dashboard.tsx` - apiClient imported
- ✅ `/frontend/src/resources/packingLists.tsx` - apiClient imported
- ✅ `/frontend/src/resources/participants.tsx` - apiClient imported

### Files Still Need Fixing

Each file needs:
1. Add import: `import apiClient from '../lib/api/apiClient';`
2. Replace fetch calls with apiClient
3. Remove Authorization header (handled by cookies)

#### High Priority (User-facing features)
- `/frontend/src/pages/Settings.tsx` (2 occurrences - lines 236, 264)
- `/frontend/src/pages/CreateCombinedOrder.tsx` (2 occurrences - lines 99, 166)
- `/frontend/src/pages/PrintOrder.tsx` (1 occurrence - line 43)
- `/frontend/src/pages/PrintPackingList.tsx` (1 occurrence - line 49)
- `/frontend/src/pages/PrintCustomerList.tsx` (1 occurrence - line 42)

#### Medium Priority (Admin features)
- `/frontend/src/resources/combinedOrders.tsx` (4 occurrences - lines 79, 121, 163, 205)
- `/frontend/src/resources/brandingSettings.tsx` (1 occurrence - line 35)

#### Files Already Have apiClient Import
- `/frontend/src/pages/Dashboard.tsx` - Still has 6 `localStorage.getItem('accessToken')` calls that need replacement

## 📝 Pattern for Replacing

### Before (using localStorage):
```typescript
const token = localStorage.getItem('accessToken');
const response = await fetch(`${API_URL}/endpoint/`, {
  headers: {
    'Authorization': `Bearer ${token}`,
  },
});
const data = await response.json();
```

### After (using apiClient):
```typescript
const response = await apiClient.get('/endpoint/');
const data = response.data;
```

## 🧪 Testing Checklist

Before deploying to production, test:

1. **Login Flow**
   - [ ] Login with valid credentials + reCAPTCHA
   - [ ] Login fails with invalid credentials
   - [ ] Login fails without completing reCAPTCHA
   - [ ] Cookies are set correctly (check DevTools → Application → Cookies)

2. **Authentication Persistence**
   - [ ] Refresh page - user remains logged in
   - [ ] Open new tab - user logged in
   - [ ] Close browser and reopen - user logged in (if within 7 days)

3. **Session Expiry**
   - [ ] Wait for access token to expire (60 minutes) - auto-refresh works
   - [ ] Force logout - error notification displays
   - [ ] After logout, redirect to login page

4. **API Calls**
   - [ ] List resources (participants, orders, etc.)
   - [ ] Create new resource
   - [ ] Update existing resource
   - [ ] Delete resource
   - [ ] Bulk operations work (bulk voucher create)

5. **CSRF Protection**
   - [ ] POST/PUT/PATCH/DELETE requests include X-CSRFToken header
   - [ ] Verify in DevTools → Network → Request Headers

6. **Print Features**
   - [ ] Print order
   - [ ] Print packing list
   - [ ] Print customer list

7. **Settings**
   - [ ] Update order window settings
   - [ ] Update branding settings

## 🔒 Security Verification

1. **No Tokens in localStorage**
   - [ ] Check DevTools → Application → Local Storage
   - [ ] Should only see: `basketful_admin_user`, `userPermissions`, `permissionsCacheTime`
   - [ ] Should NOT see: `accessToken`, `refreshToken`, `token`

2. **Cookies are HttpOnly**
   - [ ] Check DevTools → Application → Cookies
   - [ ] `access_token` cookie has HttpOnly flag ✓
   - [ ] `refresh_token` cookie has HttpOnly flag ✓
   - [ ] Cookies not accessible via JavaScript

3. **CSRF Token Present**
   - [ ] `csrftoken` cookie exists
   - [ ] X-CSRFToken header sent with mutations

## 🚀 Deployment Notes

1. **Environment Variables**
   - Ensure `RECAPTCHA_PUBLIC_KEY` and `RECAPTCHA_PRIVATE_KEY` are set in production
   - Verify `VITE_API_URL` points to correct backend
   - Check `CORS_ALLOWED_ORIGINS` includes admin frontend URL

2. **Backend Configuration**
   - Cookie domain set correctly for production
   - HTTPS enforced (secure cookies)
   - SameSite=Lax configured

3. **Backwards Compatibility**
   - Backend's `CookieJWTAuthentication` already supports fallback to Authorization headers
   - Old clients will continue working during migration period
   - Can remove fallback after all clients migrated

## 📚 Documentation

Key files created/modified:
- `/frontend/src/lib/api/apiClient.ts` - Axios client with CSRF and refresh
- `/frontend/src/pages/Login.tsx` - Custom login with reCAPTCHA
- `/frontend/src/providers/authProvider.ts` - Cookie-based auth
- `/frontend/src/providers/dataProvider.ts` - Axios-based data provider
- `/frontend/src/AdminApp.tsx` - Session expiry notification listener

Backend endpoints used:
- `POST /api/v1/auth/login/` - Sets httpOnly cookies
- `POST /api/v1/auth/logout/` - Clears cookies and blacklists refresh token
- `POST /api/v1/auth/refresh/` - Rotates tokens
- `GET /api/v1/auth/me/` - Validates session and returns user data
