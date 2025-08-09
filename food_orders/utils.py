import random
from django.contrib.auth import get_user_model

User = get_user_model()

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
    nouns = ['apple', 'river', 'tiger', 'sky', 'love', 'forest']
    return f"{random.choice(adjectives)}-{random.choice(nouns)}-{random.randint(100, 999)}"

def set_random_password_for_user(user):
    """
    Sets a memorable random password for the given unsaved User object.
    Returns the generated password.
    """
    password = generate_memorable_password()
    user.set_password(password)
    user.must_change_password = True
    return password
def generate_username_if_missing(user):
    if not user.username:
        full_name = f"{user.first_name} {user.last_name}".strip()
        user.username = generate_unique_username(full_name)
