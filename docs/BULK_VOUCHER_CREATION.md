# Bulk Voucher Creation Feature

## Overview
This feature allows Django Admin users to bulk create vouchers for all participants in a specific Program.

## Access

### From Voucher Admin
1. Navigate to **Admin → Vouchers**
2. Click the **"Bulk Create Vouchers by Program"** button in the top right

### Direct URL
- Configuration: `/admin/voucher/voucher/bulk-create/`

## Workflow

### Step 1: Configuration
Configure the bulk voucher creation:
- **Program**: Select which program's participants will receive vouchers
- **Voucher Type**: Choose between Grocery or Life vouchers
- **Vouchers per Participant**: Number of vouchers each participant receives (1-10)
- **Notes** (optional): Memo/notes added to all created vouchers

### Step 2: Preview & Confirm
Review the action before execution:
- **Summary**: Shows program, type, counts, and total vouchers
- **Participant List**: View all participants with their:
  - Customer number
  - Name & email
  - Household size
  - Account status (Ready or No Account)
- **Warnings**: Participants without accounts will be flagged
- **Confirmation Checkbox**: Required to proceed - acknowledges action is irreversible

### Step 3: Execution
Safe voucher creation with:
- **Transaction Safety**: All-or-nothing database operation
- **Validation**: Each voucher runs `full_clean()` before save
- **Error Handling**: Invalid participants are skipped, not fatal
- **Reporting**: Success and error counts with details

## Validation & Safety

### Participants Skipped
Participants are automatically skipped if:
- No `AccountBalance` exists
- Voucher validation fails (`clean()` errors)
- Unexpected errors during creation

### Error Reporting
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

## Data Integrity

### Transaction Wrapping
All voucher creation is wrapped in `transaction.atomic()` to ensure database consistency.

### Validation
Each voucher goes through:
1. Model field validation
2. `full_clean()` method call
3. Custom `clean()` validation
4. Save hooks and signals

### Audit Trail
- Vouchers include notes indicating bulk creation source
- Standard voucher fields track creation timestamp
- Admin messages provide complete audit log

## Technical Implementation

### Files Created
- `apps/voucher/forms.py` - Configuration & confirmation forms
- `apps/voucher/views.py` - Multi-step view logic
- `apps/voucher/templates/admin/voucher/bulk_voucher_configure.html`
- `apps/voucher/templates/admin/voucher/bulk_voucher_preview.html`
- `apps/voucher/templates/admin/voucher/voucher/change_list.html`

### Files Modified
- `apps/voucher/admin.py` - Added custom URLs and changelist customization

### URL Routing
- `admin:bulk_voucher_configure` - Configuration form
- `admin:bulk_voucher_preview` - Preview & confirmation
- `admin:bulk_voucher_create` - Execution endpoint

## Requirements Met

✅ **Admin UX Requirements**
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

✅ **Technical Expectations**
- Custom ModelAdmin view
- Form validation
- Preview logic separate from creation
- Idiomatic Django Admin patterns
- Readable, maintainable code

## Usage Example

### Scenario
Create 2 grocery vouchers for all participants in "Wednesday Morning" program.

### Steps
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

### Result
```
✅ Successfully created 32 voucher(s) for program 'Wednesday Morning'.
```

All participants now have 2 new "Grocery" vouchers in "Pending" state.
