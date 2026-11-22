
import logging
from django.core.exceptions import ValidationError
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver
from .models import VoucherLog
from core.client_ip import get_client_ip as _shared_client_ip

logger = logging.getLogger(__name__)

if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)


class VoucherLogger:
    """Helper to log voucher events to DB and console."""
    @staticmethod
    def debug(participant, message: str, voucher=None, user=None):
        logger.debug("[Voucher DEBUG] %s", message)
        VoucherLog.objects.create(
            participant=participant,
            voucher=voucher,
            message=message,
            log_type="DEBUG",
            user=user
        )

    @staticmethod
    def error(
        participant, 
        message: str, 
        voucher=None, 
        user=None, 
        raise_exception=False
    ):
        """Log an error message and optionally raise a ValidationError."""
        logger.error("[Voucher Log ERROR] %s", message)
        VoucherLog.objects.create(
            participant=participant,
            voucher=voucher,
            message=message,
            log_type="ERROR",
            user=user
        )
        if raise_exception:
            raise ValidationError(message)
    

def get_client_ip(request):
    """Client IP from the request, or None when no request was passed.

    authenticate() and the login signals allow request=None; a crash here
    would take down the login log and the login response with it (#136).
    The address itself comes from core.client_ip (#111): the old version
    logged the leftmost X-Forwarded-For entry, which the client controls.
    """
    return _shared_client_ip(request)


def get_user_agent(request):
    """User-Agent header (truncated to the log field), or '' with no request."""
    if request is None:
        return ''
    return request.META.get('HTTP_USER_AGENT', '')[:500]


@receiver(user_logged_in)
def log_user_login(sender, request, user, **kwargs):
    """Log successful user login."""
    from apps.account.models import Participant
    from .models import UserLoginLog
    
    # Try to find associated participant
    participant = None
    try:
        participant = Participant.objects.get(user=user)
    except Participant.DoesNotExist:
        pass
    
    UserLoginLog.objects.create(
        user=user,
        action=UserLoginLog.LOGIN,
        ip_address=get_client_ip(request),
        user_agent=get_user_agent(request),
        participant=participant
    )


@receiver(user_logged_out)
def log_user_logout(sender, request, user, **kwargs):
    """Log user logout."""
    if user:
        from apps.account.models import Participant
        from .models import UserLoginLog
        
        participant = None
        try:
            participant = Participant.objects.get(user=user)
        except Participant.DoesNotExist:
            pass
        
        UserLoginLog.objects.create(
            user=user,
            action=UserLoginLog.LOGOUT,
            ip_address=get_client_ip(request),
            user_agent=get_user_agent(request),
            participant=participant
        )


@receiver(user_login_failed)
def log_user_login_failed(sender, credentials, request, **kwargs):
    """Log failed login attempts."""
    from .models import UserLoginLog
    
    UserLoginLog.objects.create(
        username_attempted=credentials.get('username', '')[:150],
        action=UserLoginLog.FAILED_LOGIN,
        ip_address=get_client_ip(request),
        user_agent=get_user_agent(request)
    )