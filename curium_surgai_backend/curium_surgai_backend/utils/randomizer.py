from random import choice
from string import ascii_uppercase, digits


def generate_random_id():
    return "".join(choice(ascii_uppercase + digits) for _ in range(12))
