# userservices.py
import random
from typing import Optional, Generator
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import User, AbstractUser
from django.db import IntegrityError, transaction
from ..models import UserProfile
# ============================================================
# User Helpers (internal, could also live in utils.py)
# ============================================================
ADJECTIVES = ["sunny", "brave", "gentle", "fuzzy", "bright"]
NOUNS = ["apple", "river", "tiger", "sky", "love", "forest"]
PARTICIPANT_NOUNS = [
    "door", "family", "hope", "heart", "light",
    "bridge", "seed", "bloom", "gift", "path",
    "anchor", "guide",
]

def _generate_memorable_password() -> str:
    return f"{random.choice(ADJECTIVES)}-{random.choice(NOUNS)}-{random.randint(100, 999)}"

def _generate_admin_username(base_name: str) -> Generator[str, None, None]:
    base_username = base_name.lower().replace(" ", "_")
    max_length = User._meta.get_field("username").max_length - 5
    base_username = base_username[:max_length]
    counter = 1
    while True:
        yield f"{base_username}_{counter}"
        counter += 1

def _generate_participant_username(base_name: str) -> Generator[str, None, None]:
    base_username = base_name.lower().replace(" ", "_")
    max_length = User._meta.get_field("username").max_length - 5
    base_username = base_username[:max_length]

    # Random nouns first
    for _ in range(10):
        yield f"{base_username}-{random.choice(PARTICIPANT_NOUNS)}"

    # Fallback: numeric suffixes
    yield from _generate_admin_username(base_username)

# ============================================================
# User Services
# ============================================================
def set_random_password_for_user(user: AbstractUser) -> str:
    """Assign a memorable random password and flag profile for reset."""
    password = _generate_memorable_password()
    user.set_password(password)
    profile, _ = UserProfile.objects.get_or_create(user=user)
    profile.must_change_password = True
    profile.save(update_fields=["must_change_password"])
    return password

def _create_user(
    *,
    first_name: str = "",
    last_name: str = "",
    email: str = "",
    participant_name: Optional[str] = None,
    username: Optional[str] = None,
    password: Optional[str] = None,
    is_staff: bool = False,
    is_superuser: bool = False,
) -> AbstractUser:
    """Internal helper to create a user with username generation & profile."""
    full_name = f"{first_name} {last_name}".strip()
    base_name = username or (participant_name if not is_staff else full_name) or "user"
    password = password or _generate_memorable_password()

    generator = _generate_participant_username(base_name) if not is_staff else _generate_admin_username(base_name)

    for candidate_username in generator:
        try:
            with transaction.atomic():
                user, _ = User.objects.get_or_create(
                    username=candidate_username,
                    defaults={
                        "first_name": first_name,
                        "last_name": last_name,
                        "email": email,
                        "is_staff": is_staff,
                        "is_superuser": is_superuser,
                        "password": make_password(password),
                    },
                )
                profile, _ = UserProfile.objects.get_or_create(user=user)
                profile.must_change_password = True
                profile.save(update_fields=["must_change_password"])
                return user
        except IntegrityError:
            continue

    raise ValueError("Could not generate a unique username after multiple attempts.")


def create_participant_user(
    *,
    first_name: str = "",
    last_name: str = "",
    email: str = "",
    participant_name: Optional[str] = None,
    username: Optional[str] = None,
    password: Optional[str] = None,
) -> AbstractUser:
    """Public API: create a participant user account."""
    return _create_user(
        first_name=first_name,
        last_name=last_name,
        email=email,
        participant_name=participant_name,
        username=username,
        password=password,
        is_staff=False,
        is_superuser=False,
    )

def create_admin_user(
    *,
    first_name: str = "",
    last_name: str = "",
    email: str = "",
    username: Optional[str] = None,
    password: Optional[str] = None,
) -> AbstractUser:
    """Public API: create an admin/staff user account."""
    return _create_user(
        first_name=first_name,
        last_name=last_name,
        email=email,
        username=username,
        password=password,
        is_staff=True,
        is_superuser=False,
    )
