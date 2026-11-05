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
