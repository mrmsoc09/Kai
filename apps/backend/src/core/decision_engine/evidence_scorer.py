from __future__ import annotations

from dataclasses import dataclass


def _clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, float(value)))


@dataclass(frozen=True)
class EvidenceScoreInput:
    validation_present: bool
    repetition_ratio: float
    response_similarity: float
    memory_match_strength: float


class EvidenceScorer:
    """
    Deterministic evidence scorer used by hypothesis generation and decision policy.
    """

    def __init__(
        self,
        *,
        validation_weight: float = 0.45,
        repetition_weight: float = 0.20,
        response_similarity_weight: float = 0.15,
        memory_match_weight: float = 0.20,
    ) -> None:
        total_weight = (
            validation_weight
            + repetition_weight
            + response_similarity_weight
            + memory_match_weight
        )
        if total_weight <= 0:
            raise ValueError("invalid_weights")
        self._validation_weight = validation_weight / total_weight
        self._repetition_weight = repetition_weight / total_weight
        self._response_similarity_weight = response_similarity_weight / total_weight
        self._memory_match_weight = memory_match_weight / total_weight

    def score(self, signal: EvidenceScoreInput) -> float:
        validation_signal = 1.0 if signal.validation_present else 0.0
        repetition_signal = _clamp(signal.repetition_ratio)
        similarity_signal = _clamp(signal.response_similarity)
        memory_signal = _clamp(signal.memory_match_strength)
        confidence = (
            self._validation_weight * validation_signal
            + self._repetition_weight * repetition_signal
            + self._response_similarity_weight * similarity_signal
            + self._memory_match_weight * memory_signal
        )
        return round(_clamp(confidence), 4)
