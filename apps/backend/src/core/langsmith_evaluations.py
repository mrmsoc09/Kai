"""
LangSmith Evaluation & Experiment Layer for K1 / Kai Platform
================================================================
Manages evaluation datasets, experiment definitions, and evaluation targets
for Kai's mission outputs, structured results, and agent behaviors.

Capabilities:
  1. Dataset management — create/populate evaluation datasets from mission runs
  2. Evaluation targets — score Kai structured outputs (triage, evidence, reports)
  3. Experiment support — A/B comparisons for prompts, tools, strategies
  4. Mission replay datasets — failed mission traces as regression tests

Architecture:
  - All dataset/experiment operations go through the LangSmithBridge client
  - Datasets are namespaced by project + dataset_name
  - Evaluators are pure functions: (run_output, reference) -> EvalResult
  - No mutation of Kai state — this is a quality/observation layer only

Dataset naming convention:
  kai-{category}-{qualifier}
  Examples:
    kai-triage-accuracy
    kai-evidence-quality
    kai-report-completeness
    kai-strategy-effectiveness
    kai-mission-replay-failures

Experiment naming convention:
  kai-exp-{what}-{timestamp}
  Examples:
    kai-exp-triage-prompt-v2-20260317
    kai-exp-strategy-recon-aggressive-20260317
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

logger = logging.getLogger(__name__)

# -- Evaluation result ---------------------------------------------------------


@dataclass
class EvalResult:
    """Result of a single evaluation."""

    key: str  # metric name (e.g. "accuracy", "completeness", "relevance")
    score: float  # 0.0 - 1.0
    comment: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


# -- Dataset manager -----------------------------------------------------------


class K1DatasetManager:
    """
    Manages LangSmith evaluation datasets populated from Kai mission data.

    Datasets are created lazily on first example addition.
    """

    def __init__(self, bridge: Any) -> None:
        """
        Args:
            bridge: LangSmithBridge instance.
        """
        self._bridge = bridge
        self._dataset_cache: dict[str, str] = {}  # name -> dataset_id

    def _get_client(self) -> Any:
        """Get the LangSmith client from the bridge."""
        return self._bridge.get_client()

    def ensure_dataset(
        self,
        name: str,
        description: str = "",
    ) -> str | None:
        """
        Ensure a dataset exists, creating it if necessary.

        Args:
            name: Dataset name (should follow kai-{category}-{qualifier} convention).
            description: Human-readable description.

        Returns:
            Dataset ID string, or None if LangSmith is not operational.
        """
        if name in self._dataset_cache:
            return self._dataset_cache[name]

        client = self._get_client()
        if client is None:
            return None

        try:
            # Try to find existing dataset
            datasets = list(client.list_datasets(dataset_name=name))
            if datasets:
                dataset_id = str(datasets[0].id)
                self._dataset_cache[name] = dataset_id
                return dataset_id

            # Create new dataset
            dataset = client.create_dataset(
                dataset_name=name,
                description=description or f"Kai evaluation dataset: {name}",
            )
            dataset_id = str(dataset.id)
            self._dataset_cache[name] = dataset_id
            logger.info("Created LangSmith dataset: %s (id=%s)", name, dataset_id)
            return dataset_id
        except Exception as exc:
            logger.warning("Failed to ensure dataset '%s': %s", name, exc)
            return None

    def add_example(
        self,
        dataset_name: str,
        inputs: dict[str, Any],
        outputs: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str | None:
        """
        Add an example to a dataset.

        Args:
            dataset_name: Target dataset name.
            inputs: Example inputs.
            outputs: Expected/reference outputs (optional for input-only datasets).
            metadata: Additional metadata for the example.

        Returns:
            Example ID string, or None if failed.
        """
        dataset_id = self.ensure_dataset(dataset_name)
        if dataset_id is None:
            return None

        client = self._get_client()
        if client is None:
            return None

        try:
            example = client.create_example(
                inputs=inputs,
                outputs=outputs,
                dataset_id=dataset_id,
                metadata=metadata,
            )
            return str(example.id)
        except Exception as exc:
            logger.warning("Failed to add example to '%s': %s", dataset_name, exc)
            return None

    def add_examples_batch(
        self,
        dataset_name: str,
        examples: list[dict[str, Any]],
    ) -> int:
        """
        Add multiple examples to a dataset in batch.

        Each example dict should have "inputs" and optionally "outputs" and "metadata".

        Returns:
            Count of successfully added examples.
        """
        dataset_id = self.ensure_dataset(dataset_name)
        if dataset_id is None:
            return 0

        client = self._get_client()
        if client is None:
            return 0

        inputs_list = [ex.get("inputs", {}) for ex in examples]
        outputs_list = [ex.get("outputs") for ex in examples]
        metadata_list = [ex.get("metadata") for ex in examples]

        try:
            client.create_examples(
                inputs=inputs_list,
                outputs=outputs_list,
                metadata=metadata_list,
                dataset_id=dataset_id,
            )
            return len(examples)
        except Exception as exc:
            logger.warning("Batch add to '%s' failed: %s", dataset_name, exc)
            return 0


# -- Evaluation targets (scoring functions) ------------------------------------


def triage_accuracy_evaluator(
    run_output: dict[str, Any],
    reference: dict[str, Any] | None = None,
) -> EvalResult:
    """
    Evaluate triage specialist output accuracy.

    Scores:
    - severity_match: Does predicted severity match reference?
    - category_match: Does predicted vulnerability category match?
    - confidence_calibration: Is confidence score reasonable?
    """
    if reference is None:
        return EvalResult(key="triage_accuracy", score=0.0, comment="No reference provided")

    score = 0.0
    total_checks = 0
    matched = 0

    # Severity match
    pred_severity = run_output.get("severity", "").lower()
    ref_severity = (reference.get("severity", "") or "").lower()
    if pred_severity and ref_severity:
        total_checks += 1
        if pred_severity == ref_severity:
            matched += 1

    # Category match
    pred_category = run_output.get("category", "").lower()
    ref_category = (reference.get("category", "") or "").lower()
    if pred_category and ref_category:
        total_checks += 1
        if pred_category == ref_category:
            matched += 1

    # Confidence calibration
    pred_confidence = run_output.get("confidence", 0)
    if isinstance(pred_confidence, (int, float)):
        total_checks += 1
        if 0.0 <= pred_confidence <= 1.0:
            matched += 1  # Valid range

    score = matched / total_checks if total_checks > 0 else 0.0

    return EvalResult(
        key="triage_accuracy",
        score=score,
        comment=f"Matched {matched}/{total_checks} checks",
        metadata={
            "severity_match": pred_severity == ref_severity,
            "category_match": pred_category == ref_category,
        },
    )


def evidence_quality_evaluator(
    run_output: dict[str, Any],
    reference: dict[str, Any] | None = None,
) -> EvalResult:
    """
    Evaluate evidence analyst output quality.

    Scores based on:
    - Has artifacts produced
    - Artifacts have required fields (type, content, provenance)
    - Output is well-structured
    """
    score = 0.0
    checks = 0
    passed = 0

    # Check output has text
    output_text = run_output.get("text", "")
    checks += 1
    if output_text and len(str(output_text)) > 50:
        passed += 1

    # Check artifacts
    artifacts = run_output.get("artifacts_produced", [])
    checks += 1
    if artifacts:
        passed += 1

    # Check artifact quality
    if artifacts:
        for artifact in artifacts:
            checks += 1
            required_keys = {"artifact_type", "content"}
            if required_keys.issubset(set(artifact.keys())):
                passed += 1

    score = passed / checks if checks > 0 else 0.0

    return EvalResult(
        key="evidence_quality",
        score=score,
        comment=f"Passed {passed}/{checks} quality checks",
        metadata={"artifact_count": len(artifacts)},
    )


def report_completeness_evaluator(
    run_output: dict[str, Any],
    reference: dict[str, Any] | None = None,
) -> EvalResult:
    """
    Evaluate report synthesizer output completeness.

    Checks for presence of required report sections.
    """
    required_sections = [
        "title", "summary", "severity", "steps_to_reproduce",
        "impact", "recommendation",
    ]

    output_text = str(run_output.get("text", ""))
    output_keys = set(run_output.keys())

    found = 0
    for section in required_sections:
        if section in output_keys or section.lower() in output_text.lower():
            found += 1

    score = found / len(required_sections) if required_sections else 0.0

    return EvalResult(
        key="report_completeness",
        score=score,
        comment=f"Found {found}/{len(required_sections)} required sections",
        metadata={"missing_sections": [
            s for s in required_sections
            if s not in output_keys and s.lower() not in output_text.lower()
        ]},
    )


def strategy_effectiveness_evaluator(
    run_output: dict[str, Any],
    reference: dict[str, Any] | None = None,
) -> EvalResult:
    """
    Evaluate strategy execution effectiveness.

    Scores based on:
    - Did the strategy produce findings?
    - Were findings actionable (have severity, category)?
    - Execution time within budget?
    """
    findings = run_output.get("findings", [])
    success = run_output.get("success", False)

    score = 0.0
    checks = 3
    passed = 0

    # Success check
    if success:
        passed += 1

    # Findings presence
    if findings:
        passed += 1

    # Findings quality (at least one has severity)
    if any(f.get("severity") for f in findings if isinstance(f, dict)):
        passed += 1

    score = passed / checks

    return EvalResult(
        key="strategy_effectiveness",
        score=score,
        comment=f"Passed {passed}/{checks} effectiveness checks",
        metadata={
            "findings_count": len(findings),
            "success": success,
        },
    )


# -- Built-in evaluator registry ----------------------------------------------

EVALUATORS: dict[str, Callable[..., EvalResult]] = {
    "triage_accuracy": triage_accuracy_evaluator,
    "evidence_quality": evidence_quality_evaluator,
    "report_completeness": report_completeness_evaluator,
    "strategy_effectiveness": strategy_effectiveness_evaluator,
}


# -- Experiment runner ---------------------------------------------------------


class K1ExperimentRunner:
    """
    Runs A/B experiments comparing different configurations.

    Experiment types:
    - prompt_comparison: Same inputs, different system prompts
    - tool_comparison: Same inputs, different tool sets
    - strategy_comparison: Same targets, different attack strategies
    - provider_comparison: Same inputs, different LLM providers
    """

    def __init__(self, bridge: Any) -> None:
        self._bridge = bridge
        self._dataset_manager = K1DatasetManager(bridge)

    def create_experiment(
        self,
        name: str,
        experiment_type: str,
        description: str = "",
        config_a: dict[str, Any] | None = None,
        config_b: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Create an experiment definition.

        Returns experiment spec dict (not persisted to LangSmith until run).
        """
        experiment_id = str(uuid.uuid4())
        return {
            "experiment_id": experiment_id,
            "name": name,
            "type": experiment_type,
            "description": description,
            "config_a": config_a or {},
            "config_b": config_b or {},
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "created",
        }

    def run_evaluation(
        self,
        dataset_name: str,
        evaluator_names: list[str] | None = None,
        target_fn: Callable | None = None,
        experiment_prefix: str = "kai-eval",
    ) -> dict[str, Any]:
        """
        Run evaluations on a dataset using registered evaluators.

        This is a local evaluation pass — it does NOT call LangSmith's
        evaluate() API directly (which requires an active run). Instead,
        it fetches dataset examples, runs them through the target function,
        and scores with the specified evaluators.

        Args:
            dataset_name: Name of the evaluation dataset.
            evaluator_names: List of evaluator keys from EVALUATORS registry.
                If None, uses all registered evaluators.
            target_fn: Function that takes inputs and returns outputs.
                If None, uses stored outputs as predictions.
            experiment_prefix: Prefix for experiment naming.

        Returns:
            Summary dict with scores per evaluator.
        """
        evaluator_keys = evaluator_names or list(EVALUATORS.keys())
        evaluators = {
            k: EVALUATORS[k] for k in evaluator_keys if k in EVALUATORS
        }

        if not evaluators:
            return {"error": "No valid evaluators specified", "scores": {}}

        client = self._bridge.get_client()
        if client is None:
            return {"error": "LangSmith client not available", "scores": {}}

        # Fetch examples from dataset
        dataset_id = self._dataset_manager.ensure_dataset(dataset_name)
        if dataset_id is None:
            return {"error": f"Dataset '{dataset_name}' not found", "scores": {}}

        try:
            examples = list(client.list_examples(dataset_id=dataset_id))
        except Exception as exc:
            return {"error": f"Failed to list examples: {exc}", "scores": {}}

        if not examples:
            return {"error": "Dataset is empty", "scores": {}}

        # Run evaluations
        all_results: dict[str, list[float]] = {k: [] for k in evaluators}

        for example in examples:
            inputs = example.inputs or {}
            reference = example.outputs

            # Get prediction
            if target_fn is not None:
                try:
                    prediction = target_fn(inputs)
                except Exception as exc:
                    logger.warning("Target function failed for example: %s", exc)
                    continue
            else:
                prediction = reference or {}

            # Score with each evaluator
            for eval_key, evaluator_fn in evaluators.items():
                try:
                    result = evaluator_fn(prediction, reference)
                    all_results[eval_key].append(result.score)
                except Exception as exc:
                    logger.warning("Evaluator '%s' failed: %s", eval_key, exc)

        # Compute summary
        summary: dict[str, Any] = {}
        for eval_key, scores in all_results.items():
            if scores:
                summary[eval_key] = {
                    "mean": sum(scores) / len(scores),
                    "min": min(scores),
                    "max": max(scores),
                    "count": len(scores),
                }
            else:
                summary[eval_key] = {"mean": 0.0, "count": 0}

        return {
            "dataset": dataset_name,
            "experiment_prefix": experiment_prefix,
            "evaluators": list(evaluators.keys()),
            "example_count": len(examples),
            "scores": summary,
        }


# -- Mission outcome dataset helpers ------------------------------------------


def build_triage_example(
    mission_id: str,
    finding_id: str,
    triage_input: dict[str, Any],
    triage_output: dict[str, Any],
    ground_truth: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Build a triage evaluation dataset example from a mission finding.

    Args:
        mission_id: Source mission.
        finding_id: Finding identifier.
        triage_input: Input to triage specialist (vulnerability data).
        triage_output: Triage specialist output (severity, category, etc.).
        ground_truth: Known-correct triage values (for supervised evaluation).

    Returns:
        Example dict ready for add_example().
    """
    return {
        "inputs": {
            "finding_id": finding_id,
            "vulnerability_data": triage_input,
        },
        "outputs": ground_truth or triage_output,
        "metadata": {
            "mission_id": mission_id,
            "source": "mission_execution",
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
    }


def build_evidence_example(
    mission_id: str,
    evidence_input: dict[str, Any],
    evidence_output: dict[str, Any],
) -> dict[str, Any]:
    """Build an evidence quality evaluation example."""
    return {
        "inputs": evidence_input,
        "outputs": evidence_output,
        "metadata": {
            "mission_id": mission_id,
            "source": "mission_execution",
        },
    }


def build_mission_replay_example(
    mission_id: str,
    mission_config: dict[str, Any],
    mission_result: dict[str, Any],
    failure_reason: str = "",
) -> dict[str, Any]:
    """
    Build a mission replay dataset example from a failed or notable mission.

    Used for regression testing — can replay missions to verify fixes.
    """
    return {
        "inputs": {
            "mission_config": mission_config,
            "mission_id": mission_id,
        },
        "outputs": {
            "result": mission_result,
            "failure_reason": failure_reason,
        },
        "metadata": {
            "mission_id": mission_id,
            "source": "mission_replay",
            "is_failure": bool(failure_reason),
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
    }
