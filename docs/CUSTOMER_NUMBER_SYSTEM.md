# Customer Number System

> Last updated: 2026-07-13

## Overview
The customer number system generates spoken-friendly, warehouse-optimized identifiers for participants. These numbers are designed to be easily communicated verbally in noisy environments while including error detection.

## Format: C-XXX-D

- **C**: Fixed prefix meaning "Customer"
- **XXX**: 3-character code using NATO-clear consonants
- **D**: Single numeric check digit (0-9)

**Example**: `C-BKM-7`

## Design Goals

### Spoken-Friendly
- Uses only NATO-clear consonants: `BCDFGHJKMNPRTVWXY`
- Excludes easily confused letters:
  - Vowels (A, E, I, O, U) - avoid creating words
  - L, Q, S, Z - commonly misheard over radio

### Error Detection
- Check digit validates the code using weighted sum
- Catches single-character errors
- Catches transposition errors

### Warehouse Optimized
- Short enough to memorize temporarily
- Clear pronunciation over walkie-talkies
- No ambiguous characters
- Professional appearance on printed orders

## Implementation

### Files
- **apps/account/utils/warehouse_id.py** - Core generator and validator
- **apps/account/models.py** - Participant.customer_number field
- **apps/account/migrations/** - Schema and data migrations

### Auto-Generation
Customer numbers are automatically generated when:
1. New participant is created
2. Field is empty on save
3. Collision prevention ensures uniqueness (max 100 attempts)

### Algorithm

#### Check Digit Calculation
```python
def calculate_check_digit(code: str) -> int:
    """
    Weighted sum modulo 10 with weights [3, 2, 1]
    Example: "BKM" → B=0, K=7, M=8
    (0×3 + 7×2 + 8×1) = 22
    Check digit = (10 - 22%10) % 10 = 8
    """
```

#### Generation Process
1. Randomly select 3 characters from `SAFE_CHARS`
2. Calculate check digit
3. Format as `C-XXX-D`
4. Check against existing numbers
5. Retry if collision (max 100 attempts)

### Validation

```python
validate_customer_number("C-BKM-8")
# Returns: (True, "")

validate_customer_number("C-BKM-9")  # Wrong check digit
# Returns: (False, "Check digit mismatch: expected 8, got 9")

validate_customer_number("INVALID")
# Returns: (False, "Invalid format: must be C-XXX-D")
```

### Normalization (login-time input cleanup)

Participants typing a customer number from a printed card don't always type
the literal ASCII hyphen. `normalize_customer_number()` cleans up common
input variants before validation/lookup:

- En-dash (`–`), em-dash (`—`), figure-dash, minus sign, soft hyphen → ASCII hyphen
- Spaces used as separators (`C BKM 7`) → removed
- No separator at all (`CBKM7`) → reformatted to `C-BKM-7`
- Lowercase (`c-bkm-7`) → uppercased

```python
normalize_customer_number("c bkm 7")   # -> "C-BKM-7"
normalize_customer_number("C–BKM–7")   # en-dash -> "C-BKM-7"
normalize_customer_number("CBKM7")     # -> "C-BKM-7"
```

This is wired into login: `FlexibleTokenObtainPairSerializer.validate()`
(`apps/account/api/jwt_serializers.py`) calls `normalize_customer_number()`
then `validate_customer_number()` on any identifier that looks like a
customer number, before looking up the `Participant`. An invalid check digit
surfaces as a specific error (`"Check digit mismatch: expected 8, got 7"`)
rather than a generic "not found" message.

**Implementation:** `apps/account/utils/warehouse_id.py::normalize_customer_number()`

## Usage

### Login
Participants can log in with **either** their customer number or their
Django username — `FlexibleTokenObtainPairSerializer`
(`apps/account/api/jwt_serializers.py`) detects which one was entered (an
identifier starting with `C` and at least 5 characters is treated as a
customer number) and resolves it to the linked `User` account. The
onboarding email (see `apps/log` `EmailType` "onboarding") currently leads
with the username and lists the customer number as a secondary credential —
this was changed back from customer-number-first in migration
`apps/log/migrations/0017_onboarding_email_username_wording.py` (Issue #83),
since staff and participants use the username day-to-day.

### Display on Orders
Customer numbers appear on:
- Order print views
- Admin participant lists
- Cart displays
- Warehouse pick sheets
- Welcome cards printed at intake (see [BULK_PARTICIPANT_CREATE_WELCOME_CARDS.md](BULK_PARTICIPANT_CREATE_WELCOME_CARDS.md))

### Manual Entry
Warehouse staff can verify numbers by:
1. Reading the 3-letter code
2. Checking the digit matches
3. Catching typos immediately

## Capacity

- **17 consonants** in safe character set
- **17³ = 4,913** unique 3-character codes
- Plus check digit validation
- **Sufficient** for typical program sizes

## Migration

### Schema Migration
`apps/account/migrations/0002_participant_customer_number.py` adds the
`customer_number` field (`CharField`, `max_length=10`, `unique=True`,
`blank=True`, `null=True`) to `Participant`.

### Data Migration
`apps/account/migrations/0003_populate_customer_numbers.py`:
- Generates numbers for all existing participants missing one
- Tracks generated numbers within the batch to prevent in-run collisions (plus a DB existence check)
- Reversible (`reverse_populate_customer_numbers` clears all numbers back to `null`)

## Benefits

### For Warehouse Staff
- ✅ Easy to speak: "Customer Bravo Kilo Mike Seven"
- ✅ Easy to hear: Clear consonant sounds
- ✅ Easy to verify: Check digit catches errors
- ✅ Short length: Quick to communicate

### For System
- ✅ Automatic generation
- ✅ Collision prevention
- ✅ Unique constraint in database
- ✅ Migration support for existing data

### For Participants
- ✅ Professional appearance
- ✅ Privacy-friendly (not sequential)
- ✅ Memorable format
- ✅ Printed on all orders

## Technical Details

### Model Field
```python
customer_number = models.CharField(
    max_length=10,
    unique=True,
    blank=True,
    null=True,
    help_text="Customer number format: C-XXX-D (e.g., C-BKM-7)"
)
```

### Save Hook
```python
def save(self, *args, **kwargs):
    if not self.customer_number:
        from .utils.warehouse_id import generate_unique_customer_number
        self.customer_number = generate_unique_customer_number(
            existing_numbers_queryset=Participant.objects.all()
        )
    super().save(*args, **kwargs)
```

## Testing

There is currently no dedicated pytest module for
`apps/account/utils/warehouse_id.py` (no `warehouse_id`-matching tests exist
under `apps/account/tests/` as of this writing). Coverage of customer-number
generation/validation is indirect, via participant-creation tests elsewhere
in `apps/account/tests/`.

## Future Enhancements

Potential improvements:
- QR code generation for scanning
- Barcode support
- Voice recognition integration
- Mobile app lookup
