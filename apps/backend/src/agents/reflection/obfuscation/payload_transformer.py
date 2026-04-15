import base64
from .ast_mutator import NoiseGenerator
from .shellcode_envelope import ShellcodeEnvelope
from ....core.praison_execution_events import MissionEvent, get_event_bus
import logging

logger = logging.getLogger(__name__)

class PayloadTransformer:
    def __init__(self):
        self.mutator = NoiseGenerator()
        self.wrapper = ShellcodeEnvelope()

    def generate_polymorphic_variant(
        self,
        raw_payload: str,
        payload_type: str = "python",
        target_context: str = "generic",
        strategy_hint: str = "AST Mutation",
    ) -> str:
        # 1. AST/Noise Transformation
        context_prefix = f"# target_context={target_context} strategy={strategy_hint}\n"
        mutated = self.mutator.inject_noise(context_prefix + raw_payload)
        
        # 2. Binary Envelope
        if payload_type == "binary":
            mutated = base64.b64encode(self.wrapper.wrap(mutated.encode())).decode()

        # 3. Telemetry Signal
        self._emit_vrad_ghost(target_context=target_context, strategy_hint=strategy_hint)
        
        return mutated

    def _emit_vrad_ghost(self, target_context: str, strategy_hint: str):
        try:
            get_event_bus().emit(
                MissionEvent(
                    event_type="PAYLOAD_GHOST_GENERATED",
                    phase="reflection_loop",
                    detail={
                        "v-rad_visual": "IRIDESCENT_SHIMMER",
                        "target_context": target_context,
                        "strategy": strategy_hint,
                    }
                )
            )
        except Exception:
            pass
