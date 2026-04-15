import base64
from .ast_mutator import NoiseGenerator
from .shellcode_envelope import ShellcodeWrapper
from ....core.praison_execution_events import MissionEvent, get_event_bus
import logging

logger = logging.getLogger(__name__)

class PayloadTransformer:
    def __init__(self):
        self.mutator = NoiseGenerator()
        self.wrapper = ShellcodeWrapper()

    def generate_polymorphic_variant(self, raw_payload: str, payload_type: str = "python") -> str:
        # 1. AST/Noise Transformation
        mutated = self.mutator.inject_noise(raw_payload)
        
        # 2. Binary Envelope
        if payload_type == "binary":
            mutated = base64.b64encode(self.wrapper.wrap(mutated.encode())).decode()

        # 3. Telemetry Signal
        self._emit_vrad_ghost()
        
        return mutated

    def _emit_vrad_ghost(self):
        try:
            get_event_bus().emit(
                MissionEvent(
                    event_type="PAYLOAD_GHOST_GENERATED",
                    phase="reflection_loop",
                    detail={"v-rad_visual": "IRIDESCENT_SHIMMER"}
                )
            )
        except Exception:
            pass
