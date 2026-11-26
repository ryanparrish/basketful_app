"""Project-wide pytest fixtures."""
import pytest


@pytest.fixture(autouse=True)
def _legacy_participant_pages(settings):
    """
    Serve the old Django participant pages in tests.

    Production redirects them to the React app
    (core.middleware.LegacyParticipantRedirectMiddleware); the tests that
    exercise those views need them reachable. Redirect tests turn it back on.
    """
    settings.LEGACY_PARTICIPANT_REDIRECTS = False


@pytest.fixture(autouse=True, scope="session")
def _fast_password_hasher():
    """
    Hash test passwords with MD5 instead of PBKDF2.

    PBKDF2 is deliberately slow (~0.5s per hash), and factories and
    create_user hash a password for every test user, which made up most of
    the suite's runtime. MD5 still verifies passwords, so login tests
    behave the same. Never use it outside tests.

    Session-scoped rather than using the function-scoped `settings`
    fixture: TestCase.setUpTestData creates users at class setup, before
    function fixtures run, and those hashes must match too.
    """
    from django.conf import settings
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]


@pytest.fixture(autouse=True)
def _fresh_cache():
    """
    Start every test with an empty cache.

    Rate-limit counts and order backoff live in the cache and are keyed on
    user IDs, which repeat after each test's rollback, so a test could
    inherit another's request count and get a 429 it never earned.
    """
    from django.core.cache import cache
    cache.clear()
    yield
    cache.clear()
