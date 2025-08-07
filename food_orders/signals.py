# signals.py

from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Participant

@receiver(post_save, sender=Participant)
def initialize_participant(sender, instance, created, **kwargs):
    if created:
        instance.setup_account_and_vouchers()
