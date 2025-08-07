import random
from django.contrib.auth.models import User

def generate_unique_username(full_name):
    base_username = full_name.lower().replace(" ", "_")
    username = base_username
    counter = 1
    while User.objects.filter(username=username).exists():
        username = f"{base_username}_{counter}"
        counter += 1
    return username

def generate_memorable_password():
    adjectives = ['sunny', 'brave', 'gentle', 'fuzzy', 'bright']
    nouns = ['apple', 'river', 'tiger', 'sky', 'love','forest']
    return f"{random.choice(adjectives)}-{random.choice(nouns)}-{random.randint(100, 999)}"
