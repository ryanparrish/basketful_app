"""
URL configuration for the Lifeskills API.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from apps.lifeskills.api.views import (
    ProgramViewSet,
    LifeskillsCoachViewSet,
    ProgramPauseViewSet,
)

router = DefaultRouter()
router.register(r'programs', ProgramViewSet, basename='program')
router.register(r'coaches', LifeskillsCoachViewSet, basename='coach')
router.register(r'program-pauses', ProgramPauseViewSet, basename='program-pause')

urlpatterns = [
    path('', include(router.urls)),
]
