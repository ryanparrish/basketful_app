# Combined Order Creation Feature

> Last updated: January 2026

## Overview
This feature allows administrators to create combined orders by selecting a specific program and time frame. This provides more flexibility than the automated weekly combined orders.

## How to Use

### Accessing the Feature
1. Log in to the Django admin panel
2. Navigate to **Orders** → **Combined Orders**
3. Click the **"Create Combined Order"** button in the top right

### Creating a Combined Order
1. **Select Program**: Choose the program for which you want to combine orders
   - Only active programs are shown in the dropdown
   
2. **Select Time Frame**: 
   - **Start Date**: The beginning of the date range
   - **End Date**: The end of the date range
   
3. **Submit**: Click "Create Combined Order"
   - The system will find all confirmed orders for the selected program within the date range
   - If orders are found, a new combined order will be created
   - You'll see a success message with the count of orders combined
   - If no orders are found, you'll see a warning message

## What Gets Combined
The system combines:
- **Only confirmed orders** (status='confirmed')
- **Orders for the selected program** (filtered by participant's program)
- **Orders within the date range** (inclusive of start and end dates)

## Technical Details

### Files Created/Modified
1. **apps/orders/forms.py**
   - Added `CreateCombinedOrderForm` with program, start_date, and end_date fields
   - Includes validation to ensure end_date is after start_date

2. **apps/orders/admin.py**
   - Added `create_combined_order_view` method to `CombinedOrderAdmin`
   - Added custom URL route for the create view
   - Updated change_list_template

3. **apps/orders/templates/admin/orders/create_combined_order.html**
   - Custom template for the combined order creation form
   - Shows form fields and optional preview of orders

4. **apps/orders/templates/admin/orders/combinedorder/change_list.html**
   - Custom changelist template with "Create Combined Order" button

### Form Fields
- **program** (ModelChoiceField): Dropdown of active programs
- **start_date** (DateField): HTML5 date picker for start date
- **end_date** (DateField): HTML5 date picker for end date

### Validation
- Start date must be before or equal to end date
- At least one confirmed order must exist for the selected criteria

## Benefits
- **Flexibility**: Create combined orders for any time period, not just weekly
- **Program-specific**: Target specific programs for order combination
- **User-friendly**: Simple form interface with date pickers
- **Feedback**: Clear success/warning messages about what was combined
