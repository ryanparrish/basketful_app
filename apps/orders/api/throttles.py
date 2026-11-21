"""
Custom throttle classes for order submission with exponential backoff.
"""
import logging
import math
import time
from core.throttling import UserRateThrottle
from django.core.cache import cache

logger = logging.getLogger(__name__)


class OrderSubmissionThrottle(UserRateThrottle):
    """
    Throttle for order submissions with exponential backoff after failures.

    Rates (enforced together — see get_throttles on the order viewset):
    - 3 submissions per minute  (this class, scope 'order_submission')
    - 10 submissions per hour   (OrderSubmissionHourlyThrottle)
    - 50 submissions per day    (OrderSubmissionDailyThrottle)
    """
    scope = 'order_submission'
    
    def allow_request(self, request, view):
        """
        Reject while the user is in failure backoff, then apply the rate limit.

        Backoff is checked first so a request rejected by backoff does not
        also use up one of the 3-per-minute submissions.
        """
        self.backoff_remaining = 0
        if request.user and request.user.is_authenticated:
            self.backoff_remaining = get_backoff_time(request.user.id)
            if self.backoff_remaining > 0:
                logger.warning(
                    "User %s in backoff period. Remaining: %ss",
                    request.user.id, self.backoff_remaining,
                )
                return False

        return super().allow_request(request, view)

    def wait(self):
        """
        Seconds until the user may retry, used for the 429 message and the
        Retry-After header (Issue #119).

        DRF's default wait() is derived from the rate window, so a 2-second
        backoff was reported as "Expected available in 30 seconds".
        """
        if self.backoff_remaining > 0:
            return self.backoff_remaining
        return super().wait()


class OrderSubmissionHourlyThrottle(UserRateThrottle):
    """10 order submissions per hour (M8: the documented hourly cap)."""

    scope = 'order_submission_hourly'


class OrderSubmissionDailyThrottle(UserRateThrottle):
    """50 order submissions per day (M8: the documented daily cap)."""

    scope = 'order_submission_daily'


def get_backoff_time(user_id: int) -> int:
    """
    Get remaining backoff time for user in seconds.
    
    Returns:
        int: Seconds remaining in backoff period, 0 if no backoff active
    """
    cache_key = f"order_backoff:{user_id}"
    
    try:
        backoff_data = cache.get(cache_key)
        if not backoff_data:
            return 0
        
        expiry_time = backoff_data.get('expiry', 0)
        # Round up: truncating let a request through up to a second early
        # and could under-report the wait.
        remaining = math.ceil(expiry_time - time.time())
        
        return max(0, remaining)
        
    except Exception as e:
        logger.error(f"Error checking backoff for user {user_id}: {e}")
        return 0  # Allow through on error


def increment_failure_count(user_id: int) -> int:
    """
    Increment failure count and apply exponential backoff.
    
    Backoff formula: 2^n seconds (max 60s)
    Reset after 1 hour of no failures.
    
    Args:
        user_id: User ID
    
    Returns:
        int: Backoff time in seconds
    """
    cache_key = f"order_backoff:{user_id}"
    count_key = f"order_failure_count:{user_id}"
    
    try:
        # Get current failure count
        failure_count = cache.get(count_key, 0) + 1
        
        # Calculate backoff: 2^n seconds, max 60s
        backoff_seconds = min(2 ** failure_count, 60)
        
        # Set backoff expiry
        expiry_time = time.time() + backoff_seconds
        cache.set(
            cache_key,
            {'expiry': expiry_time, 'count': failure_count},
            timeout=backoff_seconds + 10  # Extra buffer
        )
        
        # Update failure count with 1 hour expiry (reset window)
        cache.set(count_key, failure_count, timeout=3600)
        
        logger.info(
            f"User {user_id} backoff: {backoff_seconds}s "
            f"(failure count: {failure_count})"
        )
        
        return backoff_seconds
        
    except Exception as e:
        logger.error(f"Error setting backoff for user {user_id}: {e}")
        return 0


def reset_failure_count(user_id: int):
    """
    Reset failure count after successful order submission.
    
    Args:
        user_id: User ID
    """
    cache_key = f"order_backoff:{user_id}"
    count_key = f"order_failure_count:{user_id}"
    
    try:
        cache.delete(cache_key)
        cache.delete(count_key)
        logger.info(f"Reset failure count for user {user_id}")
        
    except Exception as e:
        logger.error(f"Error resetting failure count for user {user_id}: {e}")
