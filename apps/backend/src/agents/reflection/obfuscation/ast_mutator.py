import random
import string

class NoiseGenerator:
    """
    Inserts non-functional, syntactically correct code blocks into payloads.
    """
    def inject_noise(self, code: str) -> str:
        noise = f"\n# {self._get_random_string(16)}\n_ = {random.randint(1000, 9999)} + {random.randint(1000, 9999)}\n"
        return code + noise

    def _get_random_string(self, length=16):
        return ''.join(random.choices(string.ascii_letters + string.digits, k=length))
