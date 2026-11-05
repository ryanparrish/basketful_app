"""Helpers for tests that sign in through the web pages."""
from apps.account.models import UserProfile


def password_already_chosen(user):
    """Mark a user as having already chosen their own password.

    New accounts (staff and participants alike) must change their password
    before using the web pages: ForcePasswordChangeMiddleware redirects them
    until UserProfile.must_change_password is cleared. Tests of other pages
    sign in as existing users, who have done that. The redirect itself is
    tested in apps/account/tests/test_bug_repros_2026_10_16.py.
    """
    UserProfile.objects.update_or_create(
        user=user, defaults={'must_change_password': False}
    )
    return user
