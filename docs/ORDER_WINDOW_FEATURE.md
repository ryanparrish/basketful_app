# Order Window Feature

> Last updated: January 2026

## Overview
This feature restricts when participants can place orders based on their class schedule. Orders can only be placed within a configurable window before their scheduled class time.

## Admin Configuration

Navigate to **Admin > Core > Order Window Settings** to configure:

- **Hours Before Class**: How many hours before class the order window opens (1-168 hours)
- **Enabled**: Toggle to enable/disable order window restrictions

**Example**: If set to 24 hours and a participant's class is Wednesday at 2:00 PM:
- Order window opens: Tuesday at 2:00 PM
- Order window closes: Wednesday at 2:00 PM

## User Experience

### When Order Window is Open
- Participants see the "Place a New Order" button enabled
- They can browse products and place orders normally

### When Order Window is Closed
- A toast notification appears showing:
  - Next class date and time
  - When the order window will open
  - Hours remaining until window opens
- The "Place a New Order" button is disabled
- Hovering over the button shows a tooltip explaining why it's disabled

## Technical Implementation

### Files Modified/Created

1. **core/models.py** - OrderWindowSettings model (singleton pattern)
2. **core/admin.py** - Admin interface for settings
3. **core/utils.py** - Utility functions for order window checking
4. **core/tests.py** - Test suite for order window functionality
5. **apps/lifeskills/views.py** - Updated participant_dashboard view
6. **apps/pantry/templates/food_orders/participant_dashboard.html** - Toast notification and button logic

### Key Functions

#### `get_next_class_datetime(participant)`
Calculates the next scheduled class datetime for a participant based on their program's meeting day and time.

#### `can_place_order(participant)`
Returns a tuple: `(bool: can_order, dict: context)`
- Checks if participant is within their order window
- Returns detailed timing information for display

### Database Migration
```bash
python manage.py migrate core
```

Creates the `core_orderwindowsettings` table.

## Testing

Run the test suite:
```bash
python -m pytest core/tests.py -xvs
```

Tests cover:
- Settings singleton pattern
- Next class datetime calculation
- Order window validation
- Context data population
- Disabled window behavior
- No program edge case

## Future Enhancements

Potential improvements:
- Per-program order window settings
- Email notifications when window opens
- Different windows for food vs hygiene products
- Grace period after class time
- Holiday/blackout date handling
