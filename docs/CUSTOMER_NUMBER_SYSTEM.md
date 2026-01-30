# Customer Number System

> Last updated: January 2026

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
validate_customer_number("C-BKM-7")
# Returns: (True, None)

validate_customer_number("C-BKM-9")  # Wrong check digit
# Returns: (False, "Invalid check digit...")

validate_customer_number("INVALID")
# Returns: (False, "Format must be C-XXX-D...")
```

## Usage

### Display on Orders
Customer numbers appear on:
- Order print views
- Admin participant lists
- Cart displays
- Warehouse pick sheets

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
```sql
ALTER TABLE account_participant 
ADD COLUMN customer_number VARCHAR(10) UNIQUE;
```

### Data Migration
- Generates numbers for all existing participants
- Tracks generated numbers to prevent collisions
- Reversible (removes all numbers)

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

Run validation tests:
```bash
pytest apps/account/tests/ -k warehouse_id
```

## Future Enhancements

Potential improvements:
- QR code generation for scanning
- Barcode support
- Voice recognition integration
- Mobile app lookup
