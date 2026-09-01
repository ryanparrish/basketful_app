# Bulk Voucher Creation Feature

> Last updated: 2026-07-13

## Overview
There are now **two independent implementations** of bulk voucher creation that both exist in the codebase today:

1. **React admin frontend** (`frontend/src/pages/BulkVoucherCreate.tsx`) — the flow reachable from the voucher list's "Create Vouchers" button in the main admin app. This is documented in detail below; it talks directly to the DRF API.
2. **Django Admin multi-step view** (`apps/voucher/forms.py`, `apps/voucher/views.py`) — an older, Program-only flow still wired into `/admin/`. Documented in "Legacy Django Admin Flow" below.

Both create real `Voucher` rows and are independently maintained — a fix or feature added to one does not automatically apply to the other.

## React Admin Frontend Flow (primary)

**File:** `frontend/src/pages/BulkVoucherCreate.tsx`, routed at `/vouchers/bulk-create` (`frontend/src/AdminApp.tsx`).

### Access
- Voucher list ("Vouchers" resource) → **"Create Vouchers"** button, or
- Voucher list → any voucher's "Create" action, which redirects to `/vouchers/bulk-create?mode=select` (see `VoucherCreate` in `frontend/src/resources/vouchers.tsx`).

### Workflow

**Step 1 — Configuration.** Choose who receives vouchers:
- **"Everyone in a Program" mode**: pick a `Program`; participants are loaded and previewed in Step 2 via `GET /api/vouchers/bulk_create/preview/?program_id=<id>`.
- **"Specific Participants" mode**: search/autocomplete participants by name or customer number and add them individually (only participants with an account balance can be added).
- Then set **Voucher Type** (Grocery/Life), **Vouchers per Participant** (1-10), and optional **Notes**.

**Step 2 — Review & Confirm.**
- Program mode shows a checkbox table of all participants in the program (pre-selected if they have an account balance); participants without an account are visibly disabled and flagged in a warning banner. Admins can deselect individual participants or use Select All / Deselect All.
- Select mode shows the list of manually-added participants.
- Submitting posts to `POST /api/vouchers/bulk_create/` with either `{program_id, participant_ids, voucher_type, quantity, notes}` or `{account_ids, voucher_type, quantity, notes}`.
- There is **no confirmation checkbox** in this flow (unlike the legacy Django Admin flow) — clicking "Create Vouchers" executes immediately.

### Server-side implementation

**Endpoint:** `VoucherViewSet.bulk_create` / `VoucherViewSet.bulk_create_preview` in `apps/voucher/api/views.py`, backed by `BulkVoucherCreateSerializer` in `apps/voucher/api/serializers.py`.

- Wrapped in `transaction.atomic()`.
- Resolves accounts either from `program_id` (+ optional `participant_ids` filter, active participants only) or directly from `account_ids`.
- Creates `quantity` vouchers per account via `Voucher.objects.create(...)` (no `full_clean()` call, and no per-participant error handling/skip-and-continue — a bad account or `DoesNotExist` raises rather than being individually reported).
- Response: `{created_count, vouchers}` where `vouchers` is `VoucherListSerializer` output.

### Related: Bulk Status Update

A separate but related feature, **Bulk Voucher Status Update** (`frontend/src/pages/BulkVoucherStatusUpdate.tsx`, routed at `/vouchers/bulk-status-update`, reachable from the voucher list's "Bulk Status Update" button), lets admins filter existing vouchers and transition many at once via `POST /api/vouchers/bulk_update_status/`. Allowed transitions: `pending → {applied, expired}`, `applied → {expired}`. See `VOUCHER_SYSTEM.md` for the full state-transition picture.

## Legacy Django Admin Flow

This is the original implementation. It still works today but is Program-only (no "specific participants" mode) and is not linked from the React frontend.

### Access

- Navigate to **Admin → Vouchers**
- Click the **"Bulk Create Vouchers by Program"** button in the top right (`apps/voucher/templates/admin/voucher/voucher/change_list.html`)
- Direct URL: `/admin/voucher/voucher/bulk-create/`

### Workflow

#### Step 1: Configuration
Configure the bulk voucher creation:
- **Program**: Select which program's participants will receive vouchers
- **Voucher Type**: Choose between Grocery or Life vouchers
- **Vouchers per Participant**: Number of vouchers each participant receives (1-10)
- **Notes** (optional): Memo/notes added to all created vouchers

#### Step 2: Preview & Confirm
Review the action before execution:
- **Summary**: Shows program, type, counts, and total vouchers
- **Participant List**: View all participants with their:
  - Customer number
  - Name & email
  - Household size
  - Account status (Ready or No Account)
- Each participant with an account balance is pre-checked; admins can deselect individual participants (or use the Select All / Deselect All buttons) before confirming — unselected participants are skipped just like ones without an account.
- **Warnings**: Participants without accounts will be flagged
- **Confirmation Checkbox**: Required to proceed - acknowledges action is irreversible

#### Step 3: Execution
Safe voucher creation with:
- **Transaction Safety**: All-or-nothing database operation
- **Validation**: Each voucher runs `full_clean()` before save
- **Error Handling**: Invalid participants are skipped, not fatal
- **Reporting**: Success and error counts with details

### Validation & Safety

Everything below this point describes the **legacy Django Admin flow only** (`apps/voucher/views.py::bulk_voucher_create`). The React frontend's `bulk_create` API action (documented above) does not skip-and-report per-participant errors, does not call `full_clean()`, and has no confirmation checkbox — it is a simpler, less defensive implementation.

#### Participants Skipped
Participants are automatically skipped if:
- No `AccountBalance` exists
- Voucher validation fails (`clean()` errors)
- Unexpected errors during creation

#### Error Reporting
After execution, admin receives:
- ✅ **Success message**: Count of vouchers created
- ⚠️ **Warning message**: Count of participants skipped
- **Detailed errors**: List of each skipped participant with reason

Example messages:
```
✅ Successfully created 32 voucher(s) for program 'Wednesday Morning'.

⚠️ 3 participant(s) were skipped due to validation or account errors. Check the details below.
• Jane Doe (#C-BKM-7): No account balance found
• John Smith (#C-TXP-2): Validation error - A consumed voucher cannot be set as active.
```

### Data Integrity

#### Transaction Wrapping
All voucher creation is wrapped in `transaction.atomic()` to ensure database consistency.

#### Validation
Each voucher goes through:
1. Model field validation
2. `full_clean()` method call
3. Custom `clean()` validation
4. Save hooks and signals

#### Audit Trail
- Vouchers include notes indicating bulk creation source
- Standard voucher fields track creation timestamp
- Admin messages provide complete audit log

### Technical Implementation

#### Files
- `apps/voucher/forms.py` - Configuration & confirmation forms
- `apps/voucher/views.py` - Multi-step view logic
- `apps/voucher/admin.py` - Custom URLs and changelist customization
- `apps/voucher/templates/admin/voucher/bulk_voucher_configure.html`
- `apps/voucher/templates/admin/voucher/bulk_voucher_preview.html`
- `apps/voucher/templates/admin/voucher/voucher/change_list.html`

#### URL Routing
- `admin:bulk_voucher_configure` - Configuration form
- `admin:bulk_voucher_preview` - Preview & confirmation
- `admin:bulk_voucher_create` - Execution endpoint

#### Requirements Met

✅ **Admin UX**
- Custom Django Admin view (not generic action)
- Accessible from voucher admin page
- Multi-step workflow: Configuration → Preview → Creation
- Hard confirmation checkbox enforced
- Clear warnings about skipped participants

✅ **Validation & Error Handling**
- Respects model-level validation
- Skips invalid participants, continues with valid
- Collects and reports all errors
- Shows success and warning counts

✅ **Data Integrity & Safety**
- Database transaction wrapping
- Model validation on each voucher
- Clear admin feedback
- Admin-only access via `@staff_member_required`

### Usage Example

#### Scenario
Create 2 grocery vouchers for all participants in "Wednesday Morning" program.

#### Steps
1. Click "Bulk Create Vouchers by Program"
2. Select:
   - Program: "Wednesday Morning"
   - Voucher Type: "Grocery"
   - Vouchers per Participant: 2
   - Notes: "Monthly grocery allocation - January 2026"
3. Click "Next: Preview Participants"
4. Review 16 participants (32 total vouchers)
5. Check confirmation: "I understand this action will create vouchers and cannot be undone"
6. Click "Create Vouchers"

#### Result
```
✅ Successfully created 32 voucher(s) for program 'Wednesday Morning'.
```

All participants now have 2 new "Grocery" vouchers in "Pending" state.
