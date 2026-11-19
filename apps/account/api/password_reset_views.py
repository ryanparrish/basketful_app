"""
Password reset API used by the participant and staff apps (#137).

Replaces Django's built-in reset pages. The emailed link still points at
/reset/<uid>/<token>/ (the staff-editable email templates build it with
{% url 'password_reset_confirm' %}); that URL now redirects into the right
app, which finishes the reset through these endpoints.

    POST auth/password-reset/           {identifier, recaptcha_token}
    POST auth/password-reset/validate/  {uid, token}
    POST auth/password-reset/confirm/   {uid, token, new_password}

None of these authenticate the caller (authentication_classes = []): a
stale session cookie must never turn a reset into a 401, which the apps'
API clients treat as an expired session (#135). Every error is a 400 with
a machine-readable ``code``.
"""
import logging

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError
from django.utils.http import urlsafe_base64_decode
from django.utils.translation import gettext as _
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

from apps.account.models import Participant, UserProfile
from apps.account.tasks.email import send_password_reset_email
from .auth_views import verify_recaptcha

logger = logging.getLogger(__name__)

User = get_user_model()

# One identifier can match several accounts (a shared household email);
# never fan out further than this from a single request.
MAX_RESET_EMAILS_PER_REQUEST = 5


class PasswordResetRateThrottle(AnonRateThrottle):
    """Reset emails per identifier from one address: stops mail-bombing one
    person. Keyed on address + identifier like LoginRateThrottle (#114)."""
    rate = '5/hour'
    scope = 'password_reset'

    def get_cache_key(self, request, view):
        data = request.data if hasattr(request.data, 'get') else {}
        identifier = str(data.get('identifier', '')).strip().lower()
        return self.cache_format % {
            'scope': self.scope,
            'ident': f'{self.get_ident(request)}:{identifier}',
        }


class PasswordResetIPRateThrottle(AnonRateThrottle):
    """Caps reset requests from one address across all identifiers. Loose
    enough for a program room that shares one address."""
    rate = '30/hour'
    scope = 'password_reset_ip'


class PasswordResetConfirmRateThrottle(AnonRateThrottle):
    """Limits link checks and password sets from one address."""
    rate = '20/minute'
    scope = 'password_reset_confirm'


def find_reset_users(identifier):
    """Active accounts with an email address that ``identifier`` names.

    An address with an @ is matched against account emails; anything else
    is a customer number, then a username (staff sign in by username).
    """
    identifier = (identifier or '').strip()
    if not identifier:
        return []

    active = User.objects.filter(is_active=True).exclude(email='')
    if '@' in identifier:
        return list(active.filter(email__iexact=identifier)
                    .order_by('pk')[:MAX_RESET_EMAILS_PER_REQUEST])

    participant = (
        Participant.objects
        .filter(customer_number__iexact=identifier, user__isnull=False)
        .select_related('user')
        .first()
    )
    if participant is not None:
        user = participant.user
        return [user] if user.is_active and user.email else []

    return list(active.filter(username__iexact=identifier)[:1])


def user_from_link(uid, token):
    """The user a reset link belongs to, or None if it is invalid or used.

    The token embeds the password hash and last login, so it stops working
    once the password is set.
    """
    try:
        pk = urlsafe_base64_decode(str(uid)).decode()
        user = User.objects.get(pk=pk)
    except (TypeError, ValueError, OverflowError, ValidationError,
            User.DoesNotExist):
        return None
    if not user.is_active:
        return None
    if not default_token_generator.check_token(user, str(token or '')):
        return None
    return user


def invalid_link_response():
    return Response(
        {'detail': _('This link is invalid or has expired.'), 'code': 'invalid_link'},
        status=status.HTTP_400_BAD_REQUEST,
    )


def end_other_sessions(user):
    """Blacklist the user's refresh tokens, so a reset signs out every
    device — the point of a reset is often that someone else knows the old
    password. Failure is logged, never raised: the new password is set."""
    try:
        from rest_framework_simplejwt.token_blacklist.models import (
            BlacklistedToken, OutstandingToken,
        )
        for outstanding in OutstandingToken.objects.filter(user=user):
            BlacklistedToken.objects.get_or_create(token=outstanding)
    except Exception:
        logger.exception('[PasswordReset] Could not end sessions for user_id=%s', user.pk)


class PasswordResetRequestView(APIView):
    """Email a reset link to the account a customer number, username or
    email address names. Always answers the same way, so it can't be used
    to find out which accounts exist."""
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [PasswordResetRateThrottle, PasswordResetIPRateThrottle]

    def post(self, request):
        ok, recaptcha_error = verify_recaptcha(request.data.get('recaptcha_token'))
        if not ok:
            return Response(
                {'detail': recaptcha_error, 'code': 'recaptcha_failed'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        identifier = str(request.data.get('identifier', '')).strip()
        if not identifier:
            return Response(
                {'detail': _('Enter your customer number or email address.'),
                 'code': 'identifier_required'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        users = find_reset_users(identifier)
        for user in users:
            send_password_reset_email.delay(user.id, force=True)
        logger.info('[PasswordReset] Requested: %d account(s) matched, user_ids=%s',
                    len(users), [u.id for u in users])

        return Response(
            {'detail': _('If an account matches, we sent it an email with a '
                         'link to set a new password.'),
             'code': 'reset_requested'},
            status=status.HTTP_202_ACCEPTED,
        )


class PasswordResetValidateView(APIView):
    """Check a reset link before showing the new-password form."""
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [PasswordResetConfirmRateThrottle]

    def post(self, request):
        if user_from_link(request.data.get('uid'), request.data.get('token')) is None:
            return invalid_link_response()
        return Response({'valid': True})


class PasswordResetConfirmView(APIView):
    """Set a new password from a reset link.

    Clears must_change_password and signs out other sessions. Returns what
    the user signs in with, so the sign-in page can fill it in.
    """
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [PasswordResetConfirmRateThrottle]

    def post(self, request):
        user = user_from_link(request.data.get('uid'), request.data.get('token'))
        if user is None:
            return invalid_link_response()

        new_password = request.data.get('new_password', '')
        try:
            validate_password(new_password, user=user)
        except ValidationError as e:
            return Response(
                {'new_password': list(e.messages), 'code': 'invalid_password'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(new_password)
        user.save(update_fields=['password'])
        UserProfile.objects.filter(user=user).update(must_change_password=False)
        end_other_sessions(user)

        participant = getattr(user, 'participant', None)
        logger.info('[PasswordReset] Password set for user_id=%s', user.pk)
        return Response({
            'message': _('Your password is set.'),
            'app': 'participant' if participant is not None else 'staff',
            'sign_in_as': getattr(participant, 'customer_number', None) or user.username,
        })
