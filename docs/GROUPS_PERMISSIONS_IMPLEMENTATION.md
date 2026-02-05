# Groups & Permissions Implementation Summary

## Overview
Implemented a comprehensive JWT-based groups and permissions system integrating Django REST Framework with React Admin. This follows industry best practices for RBAC (Role-Based Access Control) with a hybrid approach: groups in JWT token claims, detailed permissions fetched from API and cached.

## Backend Implementation (Django)

### 1. Custom JWT Serializer
**File**: `apps/account/api/jwt_serializers.py`

Created `CustomTokenObtainPairSerializer` that extends JWT tokens with:
- `username`: User's username
- `email`: User's email address
- `is_staff`: Staff status boolean
- `is_superuser`: Superuser status boolean
- `groups`: Array of group names (e.g., ["Administrators", "Order Managers"])
- `group_ids`: Array of group IDs for efficient lookups

**Token size**: ~600 bytes with 2-3 groups

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
- Updated `/api/v1/token/` to use `CustomTokenObtainPairView`
- Added `/api/v1/users/me/permissions/` endpoint

### 4. Management Command
**File**: `apps/account/management/commands/setup_groups.py`

Created `setup_groups` command that creates 7 default groups:

1. **Administrators** (169 permissions)
   - Full access to all features except superuser-only operations
   
2. **Order Managers** (16 permissions)
   - Full CRUD on orders, order items, combined orders
   - View access to participants, programs, products, categories
   
3. **Voucher Coordinators** (6 permissions)
   - Full CRUD on vouchers
   - View access to participants and programs
   
4. **Program Coordinators** (10 permissions)
   - Full CRUD on programs and participants
   - View access to vouchers and orders
   
5. **Inventory Managers** (10 permissions)
   - Full CRUD on pantry products and categories
   - View access to orders and order items
   
6. **Staff** (18 permissions)
   - Add, change, view permissions for most models (no delete)
   - Covers orders, vouchers, participants, programs, products
   
7. **Read-Only** (8 permissions)
   - View-only access to all resources

**Run**: `python manage.py setup_groups`

## Frontend Implementation (React)

### 1. Auth Provider Updates
**File**: `frontend/src/providers/authProvider.ts`

Updated `DecodedToken` interface to include:
```typescript
interface DecodedToken {
  exp: number;
  user_id: number;
  username: string;
  email?: string;
  is_staff?: boolean;
  is_superuser?: boolean;
  groups?: string[];
  group_ids?: number[];
}
```

Updated `getPermissions()` method:
- Checks localStorage cache (30-minute TTL)
- Fetches from `/api/v1/users/me/permissions/` if cache expired
- Caches response in localStorage
- Falls back to token data if API fails

Updated `logout()` to clear permissions cache

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
- **What's included**: Groups only (not detailed permissions)
- **Why**: Keeps token size manageable (~600 bytes), groups rarely change
- **Trade-off**: Need API call for detailed permissions

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
- `POST /api/v1/token/` - Get JWT access/refresh tokens (includes groups in claims)
- `POST /api/v1/token/refresh/` - Refresh access token

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
# Test JWT token includes groups
curl -X POST http://localhost:8000/api/v1/token/ \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "password"}'

# Decode JWT to verify groups claim

# Test permissions endpoint
curl http://localhost:8000/api/v1/users/me/permissions/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"

# Test groups API
curl http://localhost:8000/api/v1/groups/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### Frontend Tests
1. Log in and check JWT token includes groups
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
