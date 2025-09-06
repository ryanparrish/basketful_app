from django.db.models import F, Value, IntegerField, Case, When, BooleanField, CharField, ExpressionWrapper
from django.db.models.functions import Coalesce, Concat, Now, Extract

def program_pause_annotations(queryset):
    today = Now()
    base_reason = Coalesce(F("reason"), Value("Unnamed pause"))

    # Duration in days
    duration_seconds = Extract(F("end_date") - F("start_date"), 'epoch')
    duration_days = ExpressionWrapper(duration_seconds / 86400, output_field=IntegerField())

    # Days until start
    days_until_start_seconds = Extract(F("start_date") - today, 'epoch')
    days_until_start = ExpressionWrapper(days_until_start_seconds / 86400, output_field=IntegerField())

    annotated = queryset.annotate(
        duration=duration_days,
        days_until_start=days_until_start,
    ).annotate(
        multiplier=Case(
            When(days_until_start__gte=11, days_until_start__lte=14, duration__gte=14, then=Value(3)),
            When(days_until_start__gte=11, days_until_start__lte=14, duration__gte=1, then=Value(2)),
            default=Value(1),
            output_field=IntegerField(),
        ),
        is_active_gate=Case(
            When(multiplier__gt=1, then=Value(True)),
            default=Value(False),
            output_field=BooleanField(),
        ),
        message=Case(
            When(multiplier=3, then=Concat(Value("Extended pause: "), base_reason)),
            When(multiplier=2, then=Concat(Value("Short pause: "), base_reason)),
            default=Value("No active pause"),
            output_field=CharField(),
        )
    )

    return annotated


