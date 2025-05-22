import random

def generate_random_number(min_value=0, max_value=100):
    """Generate a random number between min_value and max_value."""
    return random.randint(min_value, max_value)
