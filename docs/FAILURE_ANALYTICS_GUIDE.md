# Order Failure Analytics - Quick Reference Guide

## Overview
New API endpoints and admin interface for monitoring and debugging failed order submissions.

## API Endpoints

### 1. Failure Analytics
**Endpoint:** `GET /api/orders/failure-analytics/`

**Authentication:** Required (Staff only)

**Query Parameters:**
- `days` (optional): Number of days to analyze (default: 7, max: 90)
- `participant_id` (optional): Filter by specific participant

**Example Requests:**
```bash
# Get last 7 days of failures
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/orders/failure-analytics/

# Get last 30 days
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/orders/failure-analytics/?days=30

# Get failures for specific participant
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/orders/failure-analytics/?participant_id=123
```

**Response Structure:**
```json
{
  "period": {
    "days": 7,
    "since": "2026-02-05T10:00:00Z",
    "until": "2026-02-12T10:00:00Z"
  },
  "summary": {
    "total_failures": 42,
    "total_orders": 458,
    "failure_rate": 8.4,
    "balance_related": 28
  },
  "common_errors": [
    {
      "error": "Food balance exceeded: $246.50 > $250.00",
      "count": 15
    },
    {
      "error": "Hygiene balance exceeded: $15.00 > $10.00",
      "count": 8
    }
  ],
  "by_day": [
    {"date": "2026-02-05", "count": 3},
    {"date": "2026-02-06", "count": 7},
    {"date": "2026-02-07", "count": 5}
  ],
  "top_participants": [
    {
      "participant__name": "John Doe",
      "participant_id": 123,
      "failure_count": 5
    }
  ]
}
```

**Use Cases:**
- Monitor overall system health
- Identify problematic error patterns
- Find participants who need support
- Track failure trends over time

---

### 2. Recent Failures
**Endpoint:** `GET /api/orders/recent-failures/`

**Authentication:** Required (Staff only)

**Query Parameters:**
- `limit` (optional): Number of records (default: 50, max: 200)
- `participant_id` (optional): Filter by specific participant

**Example Requests:**
```bash
# Get last 50 failures
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/orders/recent-failures/

# Get last 100 failures
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/orders/recent-failures/?limit=100

# Get recent failures for participant
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/orders/recent-failures/?participant_id=123
```

**Response Structure:**
```json
{
  "count": 50,
  "limit": 50,
  "results": [
    {
      "id": 1,
      "participant": 123,
      "participant_name": "John Doe",
      "user": 456,
      "idempotency_key": "d0dc77186c44fe52...",
      "cart_hash": "733fb4dbbeee66a7...",
      "total_attempted": "246.50",
      "food_total": "240.00",
      "hygiene_total": "6.50",
      "full_balance": "125.00",
      "available_balance": "250.00",
      "hygiene_balance": "10.00",
      "program_pause_active": true,
      "program_pause_name": "Weekoff",
      "voucher_multiplier": "2.0",
      "active_voucher_count": 0,
      "validation_errors": [
        "Food balance exceeded: $240.00 > $250.00"
      ],
      "validation_errors_display": "• Food balance exceeded: $240.00 > $250.00",
      "error_summary": "Food balance exceeded: $240.00 > $250.00",
      "ip_address": "192.168.1.100",
      "user_agent": "Mozilla/5.0...",
      "created_at": "2026-02-12T10:30:45Z"
    }
  ]
}
```

**Use Cases:**
- Debug specific participant issues
- Review recent error context
- Verify validation logic working correctly
- Export data for analysis

---

## Admin Interface

### Access
Navigate to: `http://localhost:8000/admin/orders/failedorderattempt/`

### Features

#### List View
- **Columns:**
  - Created At (timestamp)
  - Participant (clickable link)
  - User (clickable link)
  - Total Attempted ($)
  - Error Summary (truncated)
  - Program Pause (visual indicator)
  - Balance Status (color-coded comparison)

- **Filters:**
  - Date hierarchy (by created_at)
  - Program pause active (Yes/No)
  - Participant (dropdown)

- **Search:**
  - Participant name
  - Username
  - Error summary
  - Idempotency key
  - IP address

#### Detail View
Organized into fieldsets:

**1. Order Context**
- Participant (link to participant admin)
- User (link to user admin)
- Idempotency Key
- Created At
- IP Address
- User Agent

**2. Cart Details**
- Cart Snapshot (pretty-printed JSON)
- Cart Hash
- Total Attempted
- Food Total
- Hygiene Total

**3. Balances at Time of Failure**
- Full Balance
- Available Balance
- Hygiene Balance

**4. Program Pause Context**
- Program Pause Active (Yes/No)
- Program Pause Name
- Voucher Multiplier
- Active Voucher Count

**5. Validation Errors**
- Error Summary
- Detailed Errors (formatted list)

#### Visual Indicators

**Program Pause Status:**
- ⚠ Active (orange) - Program pause was active
- ✓ Normal (green) - Normal operations

**Balance Status:**
- Red: Food total > Available balance (exceeded)
- Green: Food total ≤ Available balance (within limit)

---

## Management Commands

### Cleanup Old Records

**Command:** `python manage.py cleanup_failed_attempts`

**Options:**
- `--days=N` - Delete records older than N days (default: 90)
- `--dry-run` - Show what would be deleted without deleting

**Examples:**
```bash
# Dry run - see what would be deleted
python manage.py cleanup_failed_attempts --days=90 --dry-run

# Actually delete records older than 90 days
python manage.py cleanup_failed_attempts --days=90

# Delete records older than 30 days
python manage.py cleanup_failed_attempts --days=30
```

**Output Example:**
```
[DRY RUN] Would delete 142 failed order attempts older than 90 days (before 2025-11-14)

Sample records:
  - 2025-08-15 | John Doe | Food balance exceeded: $240.00 > $250.00...
  - 2025-08-16 | Jane Smith | Hygiene balance exceeded: $15.00 > $10.00...
  - 2025-08-17 | Bob Johnson | Duplicate order submission detected...
  ... and 139 more
```

**Recommended Schedule:**
- Run monthly via cron job
- Keep 90 days of data (default)
- Always test with `--dry-run` first

**Cron Example:**
```cron
# Run cleanup on 1st of every month at 2am
0 2 1 * * cd /path/to/app && python manage.py cleanup_failed_attempts --days=90
```

---

## Throttling & Rate Limits

### Order Submission Limits
- **3 orders per minute** per user
- Applies to both API and traditional views
- Returns HTTP 429 (Too Many Requests) when exceeded

### Exponential Backoff
After failed order attempts:
- 1st failure: 2 seconds wait
- 2nd failure: 4 seconds wait
- 3rd failure: 8 seconds wait
- 4th failure: 16 seconds wait
- 5th+ failure: 60 seconds wait (max)

**Reset:** After 1 hour of no failures, counter resets

### Idempotency Protection
- Same cart submitted within 5 minutes = duplicate
- Idempotency key: SHA256(participant_id + cart + timestamp_minute)
- Error message: "Duplicate order submission detected. Please wait before retrying."

---

## Debugging Workflow

### Scenario: User reports "Can't submit order"

**Step 1: Check Recent Failures**
```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/orders/recent-failures/?participant_id=123&limit=5"
```

**Step 2: Review Error Context**
Look at response fields:
- `error_summary` - What validation failed?
- `available_balance` vs `food_total` - Is balance the issue?
- `program_pause_active` - Is pause causing confusion?
- `validation_errors_display` - Detailed error messages

**Step 3: Check Admin Interface**
Navigate to admin → Failed Order Attempts → Filter by participant

Review:
- Balance Status indicator (red/green)
- Program Pause indicator (⚠ Active / ✓ Normal)
- Cart Snapshot - What items were in cart?
- IP Address - Is this the right user?

**Step 4: Common Issues**

| Symptom | Likely Cause | Solution |
|---------|--------------|----------|
| "Balance exceeded" but balance looks ok | Program pause multiplier not visible to user | Explain 2x multiplier in UI |
| Multiple failures same time | Double-click submission | Idempotency working correctly |
| "Duplicate submission" | User refreshing too quickly | Ask user to wait 30 seconds |
| "Another order being processed" | Concurrent submission | Distributed lock working, retry in 10s |

---

## Monitoring Dashboard (Example)

Create custom dashboard using analytics API:

```javascript
// Fetch last 7 days analytics
const analytics = await fetch('/api/orders/failure-analytics/?days=7');
const data = await analytics.json();

// Display metrics
console.log(`Failure Rate: ${data.summary.failure_rate}%`);
console.log(`Total Failures: ${data.summary.total_failures}`);
console.log(`Balance Issues: ${data.summary.balance_related}`);

// Chart common errors
data.common_errors.forEach(err => {
  console.log(`${err.error}: ${err.count} occurrences`);
});

// Line chart: failures by day
const chartData = data.by_day.map(d => ({
  date: d.date,
  failures: d.count
}));
```

### Alert Thresholds
- **Warning:** Failure rate > 5%
- **Critical:** Failure rate > 10%
- **Info:** Specific participant > 10 failures in 1 hour

---

## Data Retention

### Default Policy
- **Failed Order Attempts:** 90 days
- **Order Validation Logs:** Permanent (in apps.log.models)

### Storage Estimates
- Average record size: ~1 KB
- Expected failures: 1-5% of orders
- For 10,000 orders/day:
  - 100-500 failed attempts/day
  - 9,000-45,000 records over 90 days
  - **Total storage: ~9-45 MB**

### Cleanup Automation
```bash
# Monthly cleanup script
#!/bin/bash
cd /path/to/basketful_app

# Dry run first
python manage.py cleanup_failed_attempts --days=90 --dry-run

# If looks good, actually cleanup
python manage.py cleanup_failed_attempts --days=90

# Log results
echo "Cleanup completed at $(date)" >> /var/log/basketful/cleanup.log
```

---

## Security Considerations

### Access Control
- **API Endpoints:** Staff only (IsStaffUser permission)
- **Admin Interface:** Staff and superuser only
- **Delete Permission:** Superuser only (audit integrity)

### Sensitive Data
- User Agent strings captured (max 500 chars)
- IP addresses logged
- Cart contents stored (product IDs only, not personal data)

### Data Privacy
- Failed attempts not visible to participants
- Only staff can view error details
- Automatic deletion after 90 days (configurable)

---

## Troubleshooting

### Redis Connection Issues
**Symptom:** Log warnings "Redis unavailable for idempotency check"

**Impact:** 
- Orders still process (graceful degradation)
- No duplicate protection or distributed locking
- No exponential backoff

**Solution:**
```bash
# Check Redis status
redis-cli ping  # Should return PONG

# Restart Redis
sudo systemctl restart redis

# Check connection in Django
python manage.py shell
>>> from django.core.cache import cache
>>> cache.set('test', 'value')
>>> cache.get('test')  # Should return 'value'
```

### High Failure Rate
**Symptom:** Failure analytics shows > 10% failure rate

**Investigation Steps:**
1. Check common errors - is one error dominating?
2. Review by_day - is this sudden or gradual?
3. Check top_participants - is it concentrated or widespread?
4. Look at balance_related count - UI showing correct info?

**Common Causes:**
- Program pause confusion (balance display issue)
- Product pricing changes
- Category limits changed
- Recent voucher policy change

### Throttle False Positives
**Symptom:** Legitimate users hitting rate limit

**Solution:**
Adjust throttle rate in `core/settings.py`:
```python
'DEFAULT_THROTTLE_RATES': {
    'order_submission': '5/minute',  # Increased from 3/minute
}
```

---

## Performance Tips

### API Response Time
- **failure_analytics** endpoint: ~100-500ms for 7 days, ~1-2s for 90 days
- **recent_failures** endpoint: ~50-200ms for 50 records

**Optimization:**
- Use smaller date ranges when possible
- Filter by participant_id for faster queries
- Indexes already optimized for common queries

### Database Growth
Monitor table size:
```sql
SELECT 
  pg_size_pretty(pg_total_relation_size('orders_failedorderattempt')) as size,
  COUNT(*) as records
FROM orders_failedorderattempt;
```

If growth exceeds expectations:
- Reduce retention period (e.g., 60 days instead of 90)
- Run cleanup more frequently (weekly instead of monthly)

---

## Future Enhancements

Potential improvements:
1. **Email alerts** when failure rate exceeds threshold
2. **Slack notifications** for critical failure patterns
3. **Real-time dashboard** with WebSocket updates
4. **Machine learning** to predict likely failures
5. **Participant-facing insights** ("Your cart is close to limit")

---

## Support

For issues or questions:
1. Check admin interface first
2. Review analytics API for patterns
3. Check logs for Redis connectivity
4. Contact development team with:
   - Participant ID
   - Timestamp of issue
   - Error message from API/admin
   - Recent failures data

---

## Changelog

### v1.0.0 (2026-02-12)
- Initial release
- FailedOrderAttempt model
- Analytics API endpoints
- Admin interface
- Cleanup management command
- Throttling with exponential backoff
- Idempotency protection
- Distributed locking
