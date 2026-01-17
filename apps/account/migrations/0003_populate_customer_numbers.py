# Generated migration - populate customer numbers for existing participants

from django.db import migrations
import random


SAFE_CHARS = "BCDFGHJKMNPRTVWXY"


def calculate_check_digit(code):
    """Calculate check digit."""
    char_values = {char: idx for idx, char in enumerate(SAFE_CHARS)}
    weights = [3, 2, 1]
    total = sum(char_values[char.upper()] * weight for char, weight in zip(code, weights))
    return (10 - (total % 10)) % 10


def generate_customer_number():
    """Generate customer number."""
    code = ''.join(random.choices(SAFE_CHARS, k=3))
    check_digit = calculate_check_digit(code)
    return f"C-{code}-{check_digit}"


def populate_customer_numbers(apps, schema_editor):
    """Generate customer numbers for all existing participants."""
    Participant = apps.get_model('account', 'Participant')
    
    # Get all participants without customer numbers
    participants_without_numbers = Participant.objects.filter(customer_number__isnull=True)
    
    if not participants_without_numbers.exists():
        print("No participants need customer numbers")
        return
    
    # Track generated numbers to avoid duplicates in this batch
    generated_numbers = set()
    
    for participant in participants_without_numbers:
        # Generate unique number
        max_attempts = 100
        for _ in range(max_attempts):
            number = generate_customer_number()
            
            # Check if already generated or exists in database
            if number not in generated_numbers and not Participant.objects.filter(customer_number=number).exists():
                participant.customer_number = number
                generated_numbers.add(number)
                break
        else:
            raise RuntimeError(f"Could not generate unique customer number for participant {participant.id}")
    
    # Bulk update for efficiency
    Participant.objects.bulk_update(participants_without_numbers, ['customer_number'])
    
    print(f"Generated customer numbers for {len(participants_without_numbers)} participants")


def reverse_populate_customer_numbers(apps, schema_editor):
    """Remove customer numbers (for rollback)."""
    Participant = apps.get_model('account', 'Participant')
    Participant.objects.update(customer_number=None)


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0002_participant_customer_number'),
    ]

    operations = [
        migrations.RunPython(populate_customer_numbers, reverse_populate_customer_numbers),
    ]
