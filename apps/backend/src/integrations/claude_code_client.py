"""
Claude Code CLI Client
Integrates Claude Code CLI for code analysis, refactoring, and repair
"""

import asyncio
import json
import logging
import os
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum

logger = logging.getLogger(__name__)


class CodeTaskType(str, Enum):
    """Types of code tasks"""
    ANALYZE = "analyze"
    REFACTOR = "refactor"
    REPAIR = "repair"
    GENERATE = "generate"
    REVIEW = "review"
    EXPLAIN = "explain"


@dataclass
class CodeTaskResult:
    """Result from Claude Code task execution"""
    task_type: CodeTaskType
    success: bool
    output: str
    changes_made: List[Dict[str, Any]] = field(default_factory=list)
    files_modified: List[str] = field(default_factory=list)
    error: Optional[str] = None
    exit_code: int = 0
    execution_time_ms: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class CodeContext:
    """Context for code task"""
    file_path: Optional[str] = None
    code_snippet: Optional[str] = None
    language: Optional[str] = None
    project_path: Optional[str] = None
    related_files: List[str] = field(default_factory=list)


class ClaudeCodeClient:
    """
    Integrate Claude Code CLI for code analysis, refactoring, and repair.
    Executes as subprocess with project context.

    Features:
    - Code analysis and vulnerability detection
    - Automated refactoring
    - Security vulnerability repair
    - Code generation from specifications
    - Code review and explanation
    """

    def __init__(
        self,
        cli_path: str = "claude",
        default_project_path: Optional[str] = None,
        timeout_seconds: int = 300
    ):
        """Initialize Claude Code client"""
        self.cli_path = cli_path
        self.default_project_path = default_project_path or os.getcwd()
        self.timeout_seconds = timeout_seconds
        self.available = False

        # Check if Claude CLI is installed
        self._verify_installation()

    def _verify_installation(self) -> bool:
        """Verify Claude Code CLI is installed and accessible"""
        try:
            result = subprocess.run(
                [self.cli_path, "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                self.available = True
                version = result.stdout.strip()
                logger.info(f"✓ Claude Code CLI available: {version}")
                return True
            else:
                self.available = False
                logger.warning(f"Claude Code CLI not responding correctly")
                return False

        except FileNotFoundError:
            self.available = False
            logger.warning(f"Claude Code CLI not found at: {self.cli_path}")
            logger.info("Install with: npm install -g @anthropic-ai/claude-code")
            return False
        except Exception as e:
            self.available = False
            logger.error(f"Error verifying Claude Code CLI: {str(e)}")
            return False

    async def execute_code_task(
        self,
        task_type: CodeTaskType,
        instruction: str,
        context: Optional[CodeContext] = None,
        project_path: Optional[str] = None,
        stream_output: bool = False
    ) -> CodeTaskResult:
        """
        Execute a code task using Claude Code CLI.

        Args:
            task_type: Type of task (analyze, refactor, repair, generate, review)
            instruction: Natural language instruction for the task
            context: Code context (file path, snippet, language)
            project_path: Project directory (defaults to current)
            stream_output: Whether to stream output in real-time

        Returns:
            CodeTaskResult with output and changes
        """
        if not self.available:
            return CodeTaskResult(
                task_type=task_type,
                success=False,
                output="",
                error="Claude Code CLI not available"
            )

        start_time = datetime.utcnow()
        context = context or CodeContext()
        project_path = project_path or self.default_project_path

        try:
            # Build command based on task type
            command = self._build_command(task_type, instruction, context, project_path)

            logger.info(f"Executing Claude Code task: {task_type.value}")
            logger.debug(f"Command: {' '.join(command)}")

            # Execute command
            if stream_output:
                result = await self._execute_streaming(command, project_path)
            else:
                result = await self._execute_standard(command, project_path)

            execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000

            # Parse result
            task_result = self._parse_result(
                task_type=task_type,
                stdout=result['stdout'],
                stderr=result['stderr'],
                exit_code=result['exit_code'],
                execution_time_ms=execution_time,
                context=context
            )

            return task_result

        except asyncio.TimeoutError:
            return CodeTaskResult(
                task_type=task_type,
                success=False,
                output="",
                error=f"Task timed out after {self.timeout_seconds} seconds"
            )
        except Exception as e:
            logger.error(f"Error executing Claude Code task: {str(e)}")
            return CodeTaskResult(
                task_type=task_type,
                success=False,
                output="",
                error=str(e)
            )

    def _build_command(
        self,
        task_type: CodeTaskType,
        instruction: str,
        context: CodeContext,
        project_path: str
    ) -> List[str]:
        """Build Claude CLI command based on task type"""

        # Base command
        command = [self.cli_path]

        # Add task-specific flags and arguments
        if task_type == CodeTaskType.ANALYZE:
            command.extend(["analyze"])
            if context.file_path:
                command.extend(["--file", context.file_path])
            elif context.code_snippet:
                # Use stdin for code snippet
                command.extend(["--stdin"])

        elif task_type == CodeTaskType.REFACTOR:
            command.extend(["refactor"])
            if context.file_path:
                command.extend(["--file", context.file_path])
            command.extend(["--instruction", instruction])

        elif task_type == CodeTaskType.REPAIR:
            command.extend(["fix"])
            if context.file_path:
                command.extend(["--file", context.file_path])
            command.extend(["--issue", instruction])
            command.extend(["--auto-apply"])  # Auto-apply fixes

        elif task_type == CodeTaskType.GENERATE:
            command.extend(["generate"])
            command.extend(["--spec", instruction])
            if context.language:
                command.extend(["--language", context.language])
            if context.file_path:
                command.extend(["--output", context.file_path])

        elif task_type == CodeTaskType.REVIEW:
            command.extend(["review"])
            if context.file_path:
                command.extend(["--file", context.file_path])
            command.extend(["--focus", instruction])

        elif task_type == CodeTaskType.EXPLAIN:
            command.extend(["explain"])
            if context.file_path:
                command.extend(["--file", context.file_path])

        # Add project context
        command.extend(["--project-dir", project_path])

        # Add related files for context
        if context.related_files:
            for related_file in context.related_files:
                command.extend(["--context-file", related_file])

        return command

    async def _execute_standard(
        self,
        command: List[str],
        cwd: str
    ) -> Dict[str, Any]:
        """Execute command and capture output"""

        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=self.timeout_seconds
            )

            return {
                'stdout': stdout.decode('utf-8'),
                'stderr': stderr.decode('utf-8'),
                'exit_code': process.returncode
            }

        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            raise

    async def _execute_streaming(
        self,
        command: List[str],
        cwd: str
    ) -> Dict[str, Any]:
        """Execute command with streaming output"""

        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd
        )

        stdout_lines = []
        stderr_lines = []

        async def read_stream(stream, lines_list):
            while True:
                line = await stream.readline()
                if not line:
                    break
                line_str = line.decode('utf-8')
                lines_list.append(line_str)
                logger.info(f"[Claude Code] {line_str.rstrip()}")

        # Read both streams concurrently
        await asyncio.gather(
            read_stream(process.stdout, stdout_lines),
            read_stream(process.stderr, stderr_lines)
        )

        await process.wait()

        return {
            'stdout': ''.join(stdout_lines),
            'stderr': ''.join(stderr_lines),
            'exit_code': process.returncode
        }

    def _parse_result(
        self,
        task_type: CodeTaskType,
        stdout: str,
        stderr: str,
        exit_code: int,
        execution_time_ms: float,
        context: CodeContext
    ) -> CodeTaskResult:
        """Parse Claude Code CLI output into structured result"""

        success = exit_code == 0
        error = stderr if exit_code != 0 else None

        # Extract changes made (look for file modification patterns)
        changes_made = []
        files_modified = []

        # Parse output for file changes
        for line in stdout.split('\n'):
            if 'Modified:' in line or 'Created:' in line or 'Fixed:' in line:
                # Extract file path
                parts = line.split(':')
                if len(parts) >= 2:
                    file_path = parts[1].strip()
                    files_modified.append(file_path)
                    changes_made.append({
                        'file': file_path,
                        'action': parts[0].strip(),
                        'description': line
                    })

        # For repair tasks, look for vulnerability fixes
        if task_type == CodeTaskType.REPAIR:
            if 'Fixed' in stdout or 'Repaired' in stdout:
                changes_made.append({
                    'type': 'security_fix',
                    'description': 'Security vulnerability repaired',
                    'details': stdout
                })

        return CodeTaskResult(
            task_type=task_type,
            success=success,
            output=stdout,
            changes_made=changes_made,
            files_modified=files_modified,
            error=error,
            exit_code=exit_code,
            execution_time_ms=execution_time_ms
        )

    # ========================================================================
    # Convenience Methods for Common Tasks
    # ========================================================================

    async def analyze_file(
        self,
        file_path: str,
        focus: Optional[str] = None
    ) -> CodeTaskResult:
        """Analyze a file for issues, security vulnerabilities, code quality"""

        instruction = focus or "Analyze for security vulnerabilities, code quality, and best practices"

        return await self.execute_code_task(
            task_type=CodeTaskType.ANALYZE,
            instruction=instruction,
            context=CodeContext(file_path=file_path)
        )

    async def repair_vulnerability(
        self,
        file_path: str,
        vulnerability_description: str,
        auto_apply: bool = True
    ) -> CodeTaskResult:
        """Repair a security vulnerability in a file"""

        instruction = f"Fix security vulnerability: {vulnerability_description}"

        return await self.execute_code_task(
            task_type=CodeTaskType.REPAIR,
            instruction=instruction,
            context=CodeContext(file_path=file_path)
        )

    async def refactor_code(
        self,
        file_path: str,
        refactoring_goal: str
    ) -> CodeTaskResult:
        """Refactor code according to specified goal"""

        return await self.execute_code_task(
            task_type=CodeTaskType.REFACTOR,
            instruction=refactoring_goal,
            context=CodeContext(file_path=file_path)
        )

    async def generate_code(
        self,
        specification: str,
        language: str,
        output_file: Optional[str] = None
    ) -> CodeTaskResult:
        """Generate code from specification"""

        return await self.execute_code_task(
            task_type=CodeTaskType.GENERATE,
            instruction=specification,
            context=CodeContext(
                language=language,
                file_path=output_file
            )
        )

    async def review_changes(
        self,
        file_path: str,
        review_focus: Optional[str] = None
    ) -> CodeTaskResult:
        """Review code changes"""

        instruction = review_focus or "Review for security, correctness, and best practices"

        return await self.execute_code_task(
            task_type=CodeTaskType.REVIEW,
            instruction=instruction,
            context=CodeContext(file_path=file_path)
        )

    async def explain_code(
        self,
        file_path: str,
        specific_section: Optional[str] = None
    ) -> CodeTaskResult:
        """Explain what code does"""

        instruction = f"Explain: {specific_section}" if specific_section else "Explain this code"

        return await self.execute_code_task(
            task_type=CodeTaskType.EXPLAIN,
            instruction=instruction,
            context=CodeContext(file_path=file_path)
        )


# Global instance
_claude_code_client: Optional[ClaudeCodeClient] = None


def get_claude_code_client() -> ClaudeCodeClient:
    """Get global Claude Code client instance"""
    global _claude_code_client
    if _claude_code_client is None:
        _claude_code_client = ClaudeCodeClient()
    return _claude_code_client


def initialize_claude_code_client(
    cli_path: str = "claude",
    project_path: Optional[str] = None
) -> ClaudeCodeClient:
    """Initialize global Claude Code client"""
    global _claude_code_client
    _claude_code_client = ClaudeCodeClient(
        cli_path=cli_path,
        default_project_path=project_path
    )
    logger.info("✓ Claude Code client initialized")
    return _claude_code_client
