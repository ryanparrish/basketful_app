"""
Custom throttle classes for order submission with exponential backoff.
"""
import logging
import time
from rest_framework.throttling import UserRateThrottle
from django.core.cache import cache

logger = logging.getLogger(__name__)


class OrderSubmissionThrottle(UserRateThrottle):
    """
    Throttle for order submissions with exponential backoff after failures.
    
    Rates:
    - 3 submissions per minute
    - 10 submissions per hour  
    - 50 submissions per day
    """
    scope = 'order_submission'
    
    def allow_request(self, request, view):
        """
        Check if request should be allowed, considering exponential backoff.
        """
        # First check standard rate limiting
        allowed = super().allow_request(request, view)
        
        if not allowed:
            return False
        
        # Check exponential backoff
        if request.user and request.user.is_authenticated:
            backoff_time = get_backoff_time(request.user.id)
            if backoff_time > 0:
                logger.warning(
                    f"User {request.user.id} in backoff period. "
                    f"Remaining: {backoff_time}s"
                )
                return False
        
        return True


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
        remaining = int(expiry_time - time.time())
        
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
