import hashlib
from typing import List

def sha256_hex(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()

def merkle_root(hashes: List[bytes]) -> bytes:
    if not hashes:
        return sha256_hex(b"EMPTY")
    layer = hashes[:]
    while len(layer) > 1:
        nxt = []
        for i in range(0, len(layer), 2):
            left = layer[i]
            right = layer[i+1] if i+1 < len(layer) else left
            nxt.append(sha256_hex(left + right))
        layer = nxt
    return layer[0]
