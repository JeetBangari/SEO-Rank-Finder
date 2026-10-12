import random
from app.config import settings

def get_next_proxy():
    """Returns a random proxy from configured settings, or None if empty."""
    if settings.PROXY_POOL:
        return random.choice(settings.PROXY_POOL)
    return None