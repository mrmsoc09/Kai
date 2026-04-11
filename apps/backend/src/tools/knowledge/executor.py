"""Knowledge-aware tool executor orchestrating execution with interpretation.

This module provides KnowledgeAwareExecutor for wrapping tool execution with
knowledge loading, parameter optimization, and automatic output interpretation.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from apps.backend.src.tools.knowledge.interpreter import ToolOutputInterpreter
from apps.backend.src.tools.knowledge.loader import ToolKnowledgeLoader

logger = logging.getLogger(__name__)


class KnowledgeAwareExecutor:
    """Orchestrates tool execution with knowledge loading and output interpretation."""

    def __init__(
        self,
        knowledge_loader: ToolKnowledgeLoader,
        interpreter: ToolOutputInterpreter,
    ) -> None:
        """Initialize with knowledge and interpretation components.

        Args:
            knowledge_loader: ToolKnowledgeLoader instance.
            interpreter: ToolOutputInterpreter instance.
        """
        self.knowledge_loader = knowledge_loader
        self.interpreter = interpreter
        self._execution_log: list[dict[str, Any]] = []

    def execute_with_knowledge(
        self,
        tool_name: str,
        target: str,
        parameters: dict[str, str] | None = None,
        timeout: int = 300,
        tool_executor: callable | None = None,
    ) -> dict[str, Any]:
        """Execute tool with knowledge injection and interpretation.

        Args:
            tool_name: Name of tool (testssl, spiderfoot, graphql-cop).
            target: Target domain/IP/host.
            parameters: Optional override parameters.
            timeout: Execution timeout in seconds.
            tool_executor: Optional callable to execute the tool.
                           If None, returns mock execution for testing.

        Returns:
            Dictionary containing:
            - tool_name: str
            - target: str
            - status: 'success' | 'failure' | 'timeout'
            - raw_output: str
            - interpreted_findings: list[dict]
            - summary: str
            - execution_time: float
            - knowledge_applied: bool
            - severity_distribution: dict[str, int]
        """
        start_time = time.time()
        status = "failure"
        raw_output = ""
        error_msg = None

        try:
            # Prepare execution context with tool knowledge
            execution_context = self._prepare_execution_context(tool_name, target, parameters)

            # Execute the tool
            raw_output, exec_time, success = self._execute_tool(
                tool_name, target, execution_context, timeout, tool_executor
            )

            if success:
                status = "success"
            else:
                status = "failure"

        except TimeoutError:
            status = "timeout"
            error_msg = f"Execution timeout after {timeout}s"
        except Exception as e:
            status = "failure"
            error_msg = str(e)
            logger.error(f"Error executing {tool_name} on {target}: {e}")

        # Interpret results
        interpreted_findings = []
        summary = ""

        if raw_output.strip():
            try:
                interpretation = self.interpreter.interpret_output(
                    tool_name, raw_output, target=target, execution_time=exec_time
                )
                interpreted_findings = interpretation.get("findings", [])
                summary = interpretation.get("summary", "")
            except Exception as e:
                logger.warning(
                    f"Error interpreting {tool_name} output: {e}. " f"Returning raw output."
                )
                # Graceful degradation: return raw output
                summary = f"Interpretation failed: {str(e)}"

        # Aggregate results
        total_time = time.time() - start_time
        result = self._aggregate_results(
            tool_name,
            target,
            status,
            raw_output,
            interpreted_findings,
            summary,
            total_time,
            error_msg,
        )

        # Log execution
        self._log_execution(
            tool_name,
            target,
            status,
            total_time,
            len(interpreted_findings),
        )

        return result

    def _prepare_execution_context(
        self,
        tool_name: str,
        target: str,
        parameters: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Prepare tool execution context with optimal parameters from knowledge.

        Args:
            tool_name: Name of the tool.
            target: Target being scanned.
            parameters: Optional override parameters.

        Returns:
            Execution-ready context dictionary.
        """
        context: dict[str, Any] = {
            "tool_name": tool_name,
            "target": target,
            "parameters": {},
        }

        try:
            # Get execution parameters from tool knowledge
            exec_params = self.knowledge_loader.get_execution_parameters(tool_name)

            # Extract critical flags
            critical_flags = exec_params.get("critical_flags", [])
            for flag_info in critical_flags:
                if isinstance(flag_info, dict):
                    flag = flag_info.get("flag")
                    if flag:
                        context["parameters"][flag] = None  # Will be filled per tool

            # Extract optional flags for this execution
            optional_flags = exec_params.get("optional_flags", [])
            for flag_info in optional_flags:
                if isinstance(flag_info, dict):
                    flag = flag_info.get("flag")
                    # Add commonly useful optional flags
                    if flag and any(x in flag for x in ["json", "output"]):
                        context["parameters"][flag] = None

        except KeyError:
            logger.warning(f"No execution parameters for {tool_name}")

        # Merge with user-provided parameters
        if parameters:
            context["parameters"].update(parameters)

        return context

    def _execute_tool(
        self,
        tool_name: str,
        target: str,
        context: dict[str, Any],
        timeout: int,
        tool_executor: callable | None,
    ) -> tuple[str, float, bool]:
        """Execute the actual tool.

        Args:
            tool_name: Name of the tool.
            target: Target being scanned.
            context: Execution context.
            timeout: Execution timeout in seconds.
            tool_executor: Optional callable to execute tool.

        Returns:
            Tuple of (output_string, execution_time_seconds, success_boolean).

        Raises:
            TimeoutError: If execution exceeds timeout.
        """
        exec_start = time.time()

        if tool_executor is None:
            # Mock execution for testing
            logger.debug(f"No tool_executor provided; using mock execution for {tool_name}")
            output = self._generate_mock_output(tool_name, target)
            exec_time = time.time() - exec_start
            return output, exec_time, True

        try:
            # Call tool executor
            output = tool_executor(tool_name, target, context, timeout)
            exec_time = time.time() - exec_start

            if exec_time > timeout:
                raise TimeoutError(f"Execution exceeded timeout of {timeout}s")

            return output, exec_time, True

        except TimeoutError:
            raise
        except Exception as e:
            exec_time = time.time() - exec_start
            logger.error(f"Tool execution failed: {e}")
            return "", exec_time, False

    def _aggregate_results(
        self,
        tool_name: str,
        target: str,
        status: str,
        raw_output: str,
        findings: list[dict[str, Any]],
        summary: str,
        execution_time: float,
        error_msg: str | None,
    ) -> dict[str, Any]:
        """Aggregate all results into final return structure.

        Args:
            tool_name: Name of the tool.
            target: Target scanned.
            status: Execution status.
            raw_output: Raw tool output.
            findings: Interpreted findings.
            summary: Interpretation summary.
            execution_time: Total execution time.
            error_msg: Optional error message.

        Returns:
            Aggregated result dictionary.
        """
        # Count findings by severity
        severity_distribution = {
            "CRITICAL": 0,
            "HIGH": 0,
            "MEDIUM": 0,
            "LOW": 0,
            "INFO": 0,
        }
        for finding in findings:
            severity = finding.get("severity", "INFO")
            if severity in severity_distribution:
                severity_distribution[severity] += 1

        result = {
            "tool_name": tool_name,
            "target": target,
            "status": status,
            "raw_output": raw_output,
            "interpreted_findings": findings,
            "summary": summary,
            "execution_time": round(execution_time, 2),
            "knowledge_applied": True,
            "severity_distribution": severity_distribution,
        }

        if error_msg:
            result["error"] = error_msg

        return result

    def _log_execution(
        self,
        tool_name: str,
        target: str,
        status: str,
        execution_time: float,
        finding_count: int,
    ) -> None:
        """Log execution details for audit/debugging.

        Args:
            tool_name: Name of the tool.
            target: Target scanned.
            status: Execution status.
            execution_time: Time in seconds.
            finding_count: Number of findings.
        """
        log_entry = {
            "tool_name": tool_name,
            "target": target,
            "status": status,
            "execution_time": execution_time,
            "finding_count": finding_count,
            "timestamp": time.time(),
        }
        self._execution_log.append(log_entry)

        logger.info(
            f"Executed {tool_name} on {target}: "
            f"status={status}, time={execution_time:.2f}s, findings={finding_count}"
        )

    @staticmethod
    def _generate_mock_output(tool_name: str, target: str) -> str:
        """Generate mock tool output for testing.

        Args:
            tool_name: Name of the tool.
            target: Target being scanned.

        Returns:
            Mock output string.
        """
        if tool_name == "testssl":
            return (
                f"Testing TLS/SSL on {target}:443\n"
                f"Protocol TLS 1.2 supported\n"
                f"Cipher Suite: AES-256-GCM - Grade A\n"
                f"Cipher Suite: AES-128-GCM - Grade A\n"
                f"Cipher Suite: DES-CBC - Grade F\n"
                f"Certificate: Valid\n"
                f"HSTS: Enabled\n"
                f"OCSP Stapling: Disabled\n"
            )
        elif tool_name == "spiderfoot":
            return (
                f"Scanning {target}\n"
                f"subdomain: api.{target}\n"
                f"subdomain: dev.{target}\n"
                f"email: admin@{target}\n"
                f"email: security@{target}\n"
                f"asn: AS12345\n"
                f"dns: A 192.0.2.1\n"
            )
        elif tool_name == "graphql-cop":
            return (
                f"Testing GraphQL endpoint: {target}/graphql\n"
                f"Introspection: enabled\n"
                f"Query depth limit: not set\n"
                f"Query complexity limit: not set\n"
                f"Batch queries: supported\n"
                f"Custom directives: 3 found\n"
            )
        else:
            return f"Mock execution for {tool_name} on {target}"

    def get_execution_log(self) -> list[dict[str, Any]]:
        """Return execution log.

        Returns:
            List of execution log entries.
        """
        return self._execution_log.copy()

    def clear_execution_log(self) -> None:
        """Clear execution log."""
        self._execution_log.clear()
