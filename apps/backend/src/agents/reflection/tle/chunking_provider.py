from __future__ import annotations
from typing import Dict, Any, List

class ChunkedMutationProvider:
    """
    K1 Chunked Transfer Provider.
    Breaks payloads into randomized chunks to defeat length/signature-based filters.
    """
    def chunk(self, payload: str, min_size: int = 1, max_size: int = 5) -> List[str]:
        chunks = []
        i = 0
        while i < len(payload):
            size = random.randint(min_size, max_size)
            chunks.append(payload[i : i + size])
            i += size
        return chunks

    def to_chunked_request(self, payload: str) -> Dict[str, Any]:
        return {
            "transfer-encoding": "chunked",
            "body": "".join([f"{len(c):x}\r\n{c}\r\n" for c in self.chunk(payload)]) + "0\r\n\r\n"
        }

import random
