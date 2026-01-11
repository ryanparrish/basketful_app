# userservices.py
from typing import Optional, Generator
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import User, AbstractUser
from django.db import IntegrityError, transaction
from apps.account.models import UserProfile
import secrets

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
    """Generate a secure and memorable password."""
    return (
        f"{secrets.choice(ADJECTIVES)}-"
        f"{secrets.choice(NOUNS)}-"
        f"{secrets.randbelow(900) + 100}"
    )

def _generate_admin_username(base_name: str) -> Generator[str, None, None]:
    """Generate admin usernames."""
    max_length = User._meta.get_field("username").max_length - 5
    base_username = base_name[:max_length]
    while True:
        yield f"{base_username}-{secrets.choice(PARTICIPANT_NOUNS)}"

def _generate_participant_username(base_name: str) -> Generator[str, None, None]:
    """Generate participant usernames."""
    max_length = User._meta.get_field("username").max_length - 5
    base_username = base_name[:max_length]
    while True:
        yield f"{base_username}-{secrets.choice(PARTICIPANT_NOUNS)}"

# ============================================================
# User Services
# ============================================================
def set_random_password_for_user(user: AbstractUser) -> str:
    """Set a secure random password for the user."""
    password = _generate_memorable_password()
    user.set_password(password)
    user.save()
    return password

def _create_user(
    *,
    username: Optional[str] = None,
    participant_name: Optional[str] = None,
    full_name: Optional[str] = None,
    first_name: str = "",
    last_name: str = "",
    email: str = "",
    password: Optional[str] = None,
    is_staff: bool = False,
    is_superuser: bool = False,
) -> AbstractUser:
    """Create a user with a unique username."""
    base_name = (
        username
        or (participant_name if not is_staff else full_name)
        or "user"
    )
    generator = (
        _generate_participant_username(base_name)
        if not is_staff
        else _generate_admin_username(base_name)
    )
    for _ in range(10):
        try:
            generated_username = next(generator)
            user = User.objects.create_user(
                username=generated_username,
                email=email,
                password=password,
            )
            user.first_name = first_name
            user.last_name = last_name
            user.is_staff = is_staff
            user.is_superuser = is_superuser
            user.save()
            return user
        except IntegrityError:
            continue
    raise ValueError(
        "Could not generate a unique username after multiple attempts."
    )

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
    username: str, full_name: str, email: str, password: str = None
) -> AbstractUser:
    """Create an admin user."""
    user = _create_user(
        username=username,
        full_name=full_name,
        email=email,
        password=password,
        is_staff=True,
        is_superuser=True,
    )
    return user
    user.save()
    return user
