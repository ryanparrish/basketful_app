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
