"""
Spoken-Friendly Customer Number Generator with Check Digit

Format: C-XXX-D
- C: Fixed prefix "Customer"
- XXX: 3-character code from NATO-clear consonants
- D: Single numeric check digit (0-9)

Design Goals:
- Easy to speak and hear in noisy warehouse environments
- Hard to misinterpret over radio/verbal communication
- Simple check digit for error detection

Example: C-BKM-7
"""

import random
from typing import Tuple


# Spoken-safe character set: NATO-clear consonants only
# Excludes: A, E, I, O, U (vowels), L, Q, S, Z (commonly misheard)
SAFE_CHARS = "BCDFGHJKMNPRTVWXY"


def calculate_check_digit(code: str) -> int:
    """
    Calculate check digit using weighted sum modulo 10.
    
    How it works:
    1. Each character gets a number (B=0, C=1, D=2, etc.)
    2. Multiply each position by a weight (first × 3, second × 2, third × 1)
    3. Add them all up
    4. The check digit makes the sum divisible by 10
    
    Args:
        code: 3-character code (e.g., "BKM")
    
    Returns:
        Single digit 0-9
    
    Example:
        code = "BKM"
        B=0, K=7, M=8
        (0×3 + 7×2 + 8×1) = 22
        Check digit = (10 - 22%10) % 10 = 8
    """
    if len(code) != 3:
        raise ValueError("Code must be exactly 3 characters")
    
    char_values = {char: idx for idx, char in enumerate(SAFE_CHARS)}
    weights = [3, 2, 1]
    
    total = sum(
        char_values[char.upper()] * weight
        for char, weight in zip(code, weights)
    )
    
    check_digit = (10 - (total % 10)) % 10
    return check_digit


def generate_customer_number() -> str:
    """
    Generate a random customer number.
    
    Returns:
        Customer number in format C-XXX-D (e.g., "C-BKM-7")
    
    Note: With 17 characters and 3 positions, there are 4,913 possible combinations.
    Collisions are handled by the caller checking uniqueness.
    """
    code = ''.join(random.choices(SAFE_CHARS, k=3))
    check_digit = calculate_check_digit(code)
    return f"C-{code}-{check_digit}"


def generate_unique_customer_number(existing_numbers_queryset=None):
    """
    Generate a unique customer number, checking against existing numbers.
    
    Args:
        existing_numbers_queryset: Queryset or set of existing customer numbers
        
    Returns:
        Unique customer number
        
    Raises:
        RuntimeError: If unable to generate unique number after max attempts
    """
    max_attempts = 100  # Prevent infinite loop
    
    for _ in range(max_attempts):
        number = generate_customer_number()
        
        # If no queryset provided, just return (database constraint will catch duplicates)
        if existing_numbers_queryset is None:
            return number
            
        # Check if number exists
        if hasattr(existing_numbers_queryset, 'filter'):
            # Django queryset
            if not existing_numbers_queryset.filter(customer_number=number).exists():
                return number
        elif hasattr(existing_numbers_queryset, '__contains__'):
            # Set or list
            if number not in existing_numbers_queryset:
                return number
    
    raise RuntimeError(
        f"Failed to generate unique customer number after {max_attempts} attempts. "
        "This may indicate the number space is exhausted."
    )


def validate_customer_number(customer_number: str) -> Tuple[bool, str]:
    """
    Validate a customer number.
    
    Args:
        customer_number: Number to validate (e.g., "C-BKM-7")
    
    Returns:
        Tuple of (is_valid, error_message)
        - (True, "") if valid
        - (False, "reason") if invalid
    
    Examples:
        >>> validate_customer_number("C-BKM-8")
        (True, "")
        
        >>> validate_customer_number("C-BKM-9")
        (False, "Check digit mismatch: expected 8, got 9")
    """
    parts = customer_number.split('-')
    if len(parts) != 3:
        return False, "Invalid format: must be C-XXX-D"
    
    prefix, code, check_str = parts
    
    if prefix != 'C':
        return False, f"Invalid prefix: must be 'C', got '{prefix}'"
    
    if len(code) != 3:
        return False, "Invalid code length: must be 3 characters"
    
    invalid_chars = [c for c in code.upper() if c not in SAFE_CHARS]
    if invalid_chars:
        return False, f"Invalid characters: {', '.join(invalid_chars)}"
    
    if not check_str.isdigit() or len(check_str) != 1:
        return False, "Invalid check digit: must be single digit 0-9"
    
    expected_check = calculate_check_digit(code)
    actual_check = int(check_str)
    
    if expected_check != actual_check:
        return False, f"Check digit mismatch: expected {expected_check}, got {actual_check}"
    
    return True, ""
