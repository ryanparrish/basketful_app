"""
Demo script to test order window functionality in Django shell.

Usage:
    python manage.py shell < demo_order_window.py
"""

from apps.account.models import Participant
from apps.lifeskills.models import Program
from core.models import OrderWindowSettings
from core.utils import can_place_order, get_next_class_datetime
from django.utils import timezone

print("\n" + "="*80)
print("ORDER WINDOW DEMO")
print("="*80)

# Get or create settings
settings = OrderWindowSettings.get_settings()
print(f"\n📋 Current Settings:")
print(f"   - Hours before class: {settings.hours_before_class}")
print(f"   - Enabled: {settings.enabled}")

# Get a participant (or use your test data)
try:
    participant = Participant.objects.first()
    if participant:
        print(f"\n👤 Testing with participant: {participant.name}")
        
        if participant.program:
            program = participant.program
            print(f"   - Program: {program.name}")
            print(f"   - Meeting day: {program.get_MeetingDay_display()}")
            print(f"   - Meeting time: {program.meeting_time}")
            
            # Get next class
            next_class = get_next_class_datetime(participant)
            if next_class:
                print(f"\n📅 Next class: {next_class.strftime('%A, %B %d, %Y at %I:%M %p')}")
            
            # Check if can order
            can_order, context = can_place_order(participant)
            
            print(f"\n🛒 Can place order: {'✅ YES' if can_order else '❌ NO'}")
            
            if context.get('window_opens'):
                print(f"   - Window opens: {context['window_opens'].strftime('%A, %B %d, %Y at %I:%M %p')}")
            
            if context.get('hours_until_open'):
                hours = context['hours_until_open']
                print(f"   - Opens in: {hours:.1f} hours ({hours/24:.1f} days)")
            
            print(f"\n⏰ Current time: {timezone.now().strftime('%A, %B %d, %Y at %I:%M %p')}")
        else:
            print("   ⚠️  No program assigned")
    else:
        print("\n⚠️  No participants found in database")
        print("   Create a participant with a program to test this feature")
        
except Exception as e:
    print(f"\n❌ Error: {e}")

print("\n" + "="*80)
print("To modify settings, go to Admin > Core > Order Window Settings")
print("="*80 + "\n")
