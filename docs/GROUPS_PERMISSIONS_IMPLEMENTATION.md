# Groups & Permissions Implementation Summary

> Last updated: 2026-07-13

## Overview
Implemented a groups and permissions system (RBAC) integrating Django REST
Framework with React Admin. Login is cookie-based: JWT access/refresh
tokens are set as httpOnly cookies and never touch client-side JavaScript.
Groups and effective permissions are **not** carried in JWT claims read by
the client — the frontend fetches them from a dedicated REST endpoint
(`GET /api/v1/users/me/permissions/`) and caches the result in
`localStorage` for 30 minutes. (An earlier design added groups directly to
JWT claims via `CustomTokenObtainPairSerializer` — that class still exists
in `jwt_serializers.py` but is not wired to any URL; the endpoints actually
used by the app resolve tokens through `FlexibleTokenObtainPairSerializer`
instead. See "Architecture Decisions" below.)

## Backend Implementation (Django)

### 1. Custom JWT Serializer
**File**: `apps/account/api/jwt_serializers.py`

`CustomTokenObtainPairSerializer` extends JWT tokens with:
- `username`: User's username
- `email`: User's email address
- `is_staff`: Staff status boolean
- `is_superuser`: Superuser status boolean
- `groups`: Array of group names (e.g., ["Administrators", "Order Managers"])
- `group_ids`: Array of group IDs for efficient lookups
- `can_bypass_order_transitions`: baked-in escape-hatch permission flag (`user.has_perm('orders.can_bypass_order_transitions')`)

**Status: not currently wired to a URL.** No view in the codebase uses
`CustomTokenObtainPairSerializer` (there is no `CustomTokenObtainPairView`).
The app's actual authentication endpoints —
`FlexibleTokenObtainPairView` (`/api/v1/token/`) and the cookie-based
`CookieTokenObtainView` (`/api/v1/auth/login/`) — both use
`FlexibleTokenObtainPairSerializer` instead, which accepts either a customer
number or a username but does **not** override `get_token()`, so its JWTs
carry only the default `rest_framework_simplejwt` claims (no groups,
no `is_staff`, no permission flags). Groups/permissions reach the frontend
exclusively through the `GET /api/v1/users/me/permissions/` endpoint
described below.

### 2. Groups & Permissions API
**File**: `apps/account/api/serializers.py`

Created three new serializers:
- **PermissionSerializer**: Shows `id`, `name`, `codename`, `app_label`, `model`
- **GroupSerializer**: Includes `permissions`, `permission_details` (nested), `user_count`
- **UserSerializer Extended**: Added `groups`, `group_details`, `user_permissions`, `all_permissions`

**File**: `apps/account/api/views.py`

Created three new viewsets:
- **GroupViewSet**: Full CRUD for groups with `prefetch_related('permissions')`
- **PermissionViewSet**: Read-only, filterable by `app_label` and `model`
- **UserViewSet.my_permissions**: Action at `/api/v1/users/me/permissions/` returns user's effective permissions

### 3. URL Configuration
**Files**: `apps/account/api/urls.py`, `apps/api/urls.py`

- Registered `/api/v1/groups/` and `/api/v1/permissions/` routes
- `/api/v1/token/` uses `FlexibleTokenObtainPairView` (customer-number-or-username login, plain JWT response body — not the cookie flow, not `CustomTokenObtainPairSerializer`)
- Added `/api/v1/users/me/permissions/` endpoint (`UserViewSet.my_permissions`)
- The production React Admin app logs in via the cookie-based
  `/api/v1/auth/login/`, `/api/v1/auth/refresh/`, `/api/v1/auth/logout/`,
  `/api/v1/auth/me/` endpoints (`apps/account/api/auth_views.py`), not
  `/api/v1/token/`

### 4. Management Command
**File**: `apps/account/management/commands/setup_groups.py`

`setup_groups` creates 7 default groups (`apps/account/management/commands/setup_groups.py`):

1. **Administrators**
   - All `Permission` objects in the database (`Permission.objects.all()`) — this
     grows automatically as new apps/models are added, so the exact count is
     not fixed and should not be treated as a stable number
   
2. **Order Managers**
   - Full CRUD on `orders.order`, `orders.orderitem`, `orders.combinedorder`
   - View access to `account.participant`, `lifeskills.program`, `pantry.product`, `pantry.category`
   
3. **Voucher Coordinators**
   - Full CRUD on `voucher.voucher`
   - View access to `account.participant`, `lifeskills.program`
   
4. **Program Coordinators**
   - Full CRUD on `lifeskills.program`, `account.participant`
   - View access to `voucher.voucher`, `orders.order`
   
5. **Inventory Managers**
   - Full CRUD on `pantry.product`, `pantry.category`
   - View access to `orders.order`, `orders.orderitem`
   
6. **Staff**
   - Add/change/view (no delete) on `orders.order`, `orders.orderitem`, `voucher.voucher`, `account.participant`, `lifeskills.program`, `pantry.product`
   
7. **Read-Only**
   - View-only on `orders.order`, `orders.orderitem`, `orders.combinedorder`, `voucher.voucher`, `account.participant`, `lifeskills.program`, `pantry.product`, `pantry.category`

Re-running the command clears and recreates permissions on existing groups
(`group.permissions.clear()` then re-add), so it's safe to re-run after
adding new models/permissions.

**Run**: `python manage.py setup_groups`

## Frontend Implementation (React)

### 1. Auth Provider Updates
**File**: `frontend/src/providers/authProvider.ts`

There is no client-side JWT decoding — tokens live in httpOnly cookies set
by the backend and are never read by JavaScript. `login()` posts
`username`/`password`/`recaptcha_token` to `/auth/login/`; the response body
contains a `user` object (not a JWT) which is cached in `localStorage` under
`basketful_admin_user`:

```typescript
interface UserData {
  id: number;
  username: string;
  email: string;
  is_staff: boolean;
  is_superuser: boolean;
  groups?: string[];
  group_ids?: number[];
}
```

`getPermissions()`:
- Checks a `localStorage` cache (`userPermissions` / `permissionsCacheTime`, 30-minute TTL)
- Fetches from `GET /api/v1/users/me/permissions/` if the cache is missing or expired, and caches the response
- On fetch failure, falls back to `{ groups, group_ids, is_staff, is_superuser }` from the cached `UserData` plus an empty `permissions` array (note: the `/auth/login/` response and the `/users/me/permissions/` endpoint don't actually populate `group_ids` today — only `groups` by name — so this fallback field is typically empty)

`logout()` calls `POST /auth/logout/` and clears the cached user and permissions from `localStorage`. `checkAuth()` verifies the session via `GET /auth/me/` on each app load.

### 2. Permission Context
**File**: `frontend/src/contexts/PermissionContext.tsx`

Created `PermissionProvider` React Context with:

**State**:
```typescript
interface PermissionData {
  groups: string[];
  group_ids: number[];
  is_staff: boolean;
  is_superuser: boolean;
  permissions: string[];
}
```

**Helper Functions**:
- `hasPermission(permission: string)`: Check single permission
- `hasAnyPermission(permissions: string[])`: Check if user has any of the listed permissions
- `hasGroup(group: string)`: Check group membership
- `isStaff`: Boolean for staff status
- `isSuperuser`: Boolean for superuser status
- `refetch()`: Clear cache and reload permissions

**Usage**:
```typescript
import { usePermissionContext } from './contexts/PermissionContext';

const { hasPermission, isStaff } = usePermissionContext();

if (hasPermission('orders.add_order')) {
  // Show create button
}
```

### 3. Groups Resource
**File**: `frontend/src/resources/groups.tsx`

Created full CRUD interface for groups:
- **List**: Shows group name, permission count, user count
- **Show**: Displays group details with permission chips
- **Edit**: Name field + permission selector
- **Create**: Same as edit

Uses `ReferenceArrayInput` with `SelectArrayInput` for permission selection

### 4. Permissions Resource
**File**: `frontend/src/resources/permissions.tsx`

Created read-only interface for permissions:
- **List**: Filterable by app label, shows all permission details
- **Show**: Displays permission metadata
- **FilterList**: Sidebar filters for Orders, Voucher, Account, Lifeskills, Pantry, Auth

### 5. Users Resource
**File**: `frontend/src/resources/users.tsx`

Created full CRUD interface for users:
- **List**: Shows username, email, staff status, group count
- **Show**: Tabbed layout with Basic Info, Groups, Permissions tabs
  - Displays effective permissions (with "All Permissions" for superusers)
  - Shows group chips
- **Edit**: Username (disabled), email, first/last name, staff status, group selection
- **Create**: All fields plus password

### 6. Admin App Integration
**File**: `frontend/src/AdminApp.tsx`

- Wrapped Admin component with `<PermissionProvider>`
- Added three new resources with icons:
  - `users` (ManageAccountsIcon)
  - `groups` (GroupIcon)
  - `permissions` (SecurityIcon)

## Architecture Decisions

### JWT Token Structure
- **What's actually included today**: Nothing beyond the default SimpleJWT
  claims. The live login endpoints (`/api/v1/auth/login/` and
  `/api/v1/token/`) both authenticate through
  `FlexibleTokenObtainPairSerializer`, which does not override `get_token()`.
  `CustomTokenObtainPairSerializer` (which *would* add `groups`, `group_ids`,
  `is_staff`, `is_superuser`, `can_bypass_order_transitions` to the token)
  is defined but unused — no view references it.
- **How the frontend actually gets groups/permissions**: a dedicated
  `GET /api/v1/users/me/permissions/` call, cached client-side. Tokens
  themselves stay in httpOnly cookies and are never inspected by JS.
- **Trade-off**: An extra network round-trip for permissions on cache miss, but simpler than keeping JWT claims and DB state in sync, and it means permission changes take effect within the 30-minute cache window without needing the user to log out/in.

### Permission Caching
- **Strategy**: 30-minute localStorage cache
- **Why**: Reduce API calls, improve performance
- **Invalidation**: Manual via `refetch()`, or on logout

### Superuser Handling
- **Backend**: Returns `['*']` for all_permissions if user.is_superuser
- **Frontend**: `hasPermission()` always returns true for superusers
- **Why**: Django's built-in behavior, consistent with ORM

### Group Assignment
- **Model**: Users can be in multiple groups
- **Permission Resolution**: Union of all group permissions + direct user permissions
- **Superuser Bypass**: Superusers automatically have all permissions

## API Endpoints

### Authentication
- `POST /api/v1/auth/login/` - Cookie-based login (requires `recaptcha_token`); sets httpOnly `access_token`/`refresh_token` cookies, returns `user` in the response body. **This is what the React Admin app actually uses.**
- `POST /api/v1/auth/refresh/` - Rotates the refresh token cookie
- `POST /api/v1/auth/logout/` - Blacklists the refresh token, clears cookies
- `GET /api/v1/auth/me/` - Returns the current user + linked participant
- `POST /api/v1/token/` - Legacy/direct JWT endpoint (`FlexibleTokenObtainPairView`); returns access/refresh tokens in the response body instead of cookies. Does **not** include groups in claims (see Architecture Decisions above).
- `POST /api/v1/token/refresh/` - Refresh access token via the body-based flow

### Groups & Permissions
- `GET /api/v1/groups/` - List all groups
- `POST /api/v1/groups/` - Create group
- `GET /api/v1/groups/{id}/` - Get group details
- `PUT /api/v1/groups/{id}/` - Update group
- `DELETE /api/v1/groups/{id}/` - Delete group
- `GET /api/v1/permissions/` - List all permissions (filterable)
- `GET /api/v1/permissions/{id}/` - Get permission details
- `GET /api/v1/users/me/permissions/` - Get current user's effective permissions

### Users
- `GET /api/v1/users/` - List all users
- `POST /api/v1/users/` - Create user
- `GET /api/v1/users/{id}/` - Get user details (includes groups, permissions)
- `PUT /api/v1/users/{id}/` - Update user
- `DELETE /api/v1/users/{id}/` - Delete user

## Testing

### Backend Tests
```bash
# Get tokens via the direct JWT endpoint (body-based, no cookies, no groups in claims)
curl -X POST http://localhost:8000/api/v1/token/ \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "password"}'

# Test permissions endpoint (this is where groups/permissions actually come from)
curl http://localhost:8000/api/v1/users/me/permissions/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"

# Test groups API
curl http://localhost:8000/api/v1/groups/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

Note: the real login path (`/api/v1/auth/login/`) requires a
`recaptcha_token` and returns tokens as httpOnly cookies rather than in the
response body, so it isn't directly curl-friendly without a valid reCAPTCHA
token (or the `test-private-key` bypass — see `verify_recaptcha()` in
`apps/account/api/auth_views.py`).

### Frontend Tests
1. Log in and confirm `localStorage['userPermissions']` is populated after the `/users/me/permissions/` call (not from decoding a token — there isn't one to decode client-side)
2. Navigate to Users, Groups, Permissions resources
3. Create a new group, assign permissions
4. Create a user, assign to groups
5. Log in as that user and verify permissions

## Future Enhancements

1. **Permission-Based UI Rendering**
   - Hide/show menu items based on permissions
   - Disable actions based on permissions
   - Use `<PermissionGate>` component wrapper

2. **Audit Logging**
   - Track permission changes
   - Log group membership changes
   - Record permission checks

3. **Custom Permissions**
   - Row-level permissions
   - Object-level permissions
   - Dynamic permissions based on data

4. **Permission Templates**
   - Pre-configured permission sets
   - Import/export group configurations

## Documentation
- Django Permissions: https://docs.djangoproject.com/en/5.2/topics/auth/default/#permissions-and-authorization
- DRF Permissions: https://www.django-rest-framework.org/api-guide/permissions/
- Simple JWT: https://django-rest-framework-simplejwt.readthedocs.io/
- React Admin Auth: https://marmelab.com/react-admin/Authentication.html
- React Admin Permissions: https://marmelab.com/react-admin/Authorization.html
