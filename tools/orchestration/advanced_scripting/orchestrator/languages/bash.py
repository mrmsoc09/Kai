"""
Bash/Shell script handler.
"""
import subprocess
import time
import os
from pathlib import Path
from typing import Optional

from .base import BaseLanguageHandler, LanguageContext, ExecutionResult


class BashHandler(BaseLanguageHandler):
    """Handler for Bash scripts."""
    
    @property
    def file_extension(self) -> str:
        return ".sh"
    
    def validate_syntax(self, content: str) -> tuple[bool, Optional[str]]:
        """Validate bash syntax using bash -n."""
        try:
            result = subprocess.run(
                ["bash", "-n"],
                input=content.encode(),
                capture_output=True,
                timeout=5
            )
            if result.returncode == 0:
                return True, None
            else:
                return False, result.stderr.decode()
        except Exception as e:
            return False, str(e)
    
    def prepare(self, context: LanguageContext) -> bool:
        """Make script executable."""
        try:
            context.script_path.chmod(0o755)
            return True
        except Exception as e:
            print(f"Failed to prepare bash script: {e}")
            return False
    
    def execute(self, context: LanguageContext) -> ExecutionResult:
        """Execute bash script."""
        cmd = ["bash", str(context.script_path)] + context.arguments
        
        start_time = time.time()
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=context.timeout,
                cwd=str(context.working_dir),
                env={**os.environ, **context.environment}
            )
            
            duration = (time.time() - start_time) * 1000
            
            return ExecutionResult(
                success=result.returncode == 0,
                exit_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                duration_ms=duration,
                resource_stats={}
            )
            
        except subprocess.TimeoutExpired:
            return ExecutionResult(
                success=False,
                exit_code=-1,
                stdout="",
                stderr="Execution timed out",
                duration_ms=context.timeout * 1000,
                resource_stats={"timeout_triggered": True}
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                exit_code=-1,
                stdout="",
                stderr=str(e),
                duration_ms=(time.time() - start_time) * 1000,
                resource_stats={"error": str(e)}
            )
