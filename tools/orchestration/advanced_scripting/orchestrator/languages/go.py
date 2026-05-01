"""
Go language handler.
"""
import subprocess
import time
import os
from pathlib import Path
from typing import Optional

from .base import BaseLanguageHandler, LanguageContext, ExecutionResult


class GoHandler(BaseLanguageHandler):
    """Handler for Go scripts/programs."""
    
    @property
    def file_extension(self) -> str:
        return ".go"
    
    def validate_syntax(self, content: str) -> tuple[bool, Optional[str]]:
        """Validate Go syntax using gofmt."""
        try:
            result = subprocess.run(
                ["gofmt", "-e"],
                input=content.encode(),
                capture_output=True,
                timeout=10
            )
            if result.returncode == 0:
                return True, None
            else:
                return False, result.stderr.decode()
        except FileNotFoundError:
            return False, "Go compiler not found"
        except Exception as e:
            return False, str(e)
    
    def prepare(self, context: LanguageContext) -> bool:
        """Initialize Go module if needed."""
        # Check if go.mod exists, if not create temporary module
        if not (context.working_dir / "go.mod").exists():
            try:
                subprocess.run(
                    ["go", "mod", "init", "temp"],
                    cwd=str(context.working_dir),
                    capture_output=True,
                    timeout=10
                )
                return True
            except Exception as e:
                print(f"Failed to initialize Go module: {e}")
                return False
        return True
    
    def execute(self, context: LanguageContext) -> ExecutionResult:
        """Compile and execute Go program."""
        binary_name = "script_bin"
        binary_path = context.working_dir / binary_name
        
        # Compile
        compile_start = time.time()
        try:
            compile_result = subprocess.run(
                ["go", "build", "-o", str(binary_path), str(context.script_path)],
                cwd=str(context.working_dir),
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if compile_result.returncode != 0:
                return ExecutionResult(
                    success=False,
                    exit_code=compile_result.returncode,
                    stdout="",
                    stderr=f"Compilation failed:\n{compile_result.stderr}",
                    duration_ms=(time.time() - compile_start) * 1000,
                    resource_stats={}
                )
            
            # Execute
            exec_start = time.time()
            run_result = subprocess.run(
                [str(binary_path)] + context.arguments,
                capture_output=True,
                text=True,
                timeout=context.timeout,
                cwd=str(context.working_dir),
                env={**os.environ, **context.environment}
            )
            
            total_duration = (time.time() - compile_start) * 1000
            
            # Cleanup binary
            if binary_path.exists():
                binary_path.unlink()
            
            return ExecutionResult(
                success=run_result.returncode == 0,
                exit_code=run_result.returncode,
                stdout=run_result.stdout,
                stderr=run_result.stderr,
                duration_ms=total_duration,
                resource_stats={"compile_time_ms": (exec_start - compile_start) * 1000}
            )
            
        except subprocess.TimeoutExpired:
            if binary_path.exists():
                binary_path.unlink()
            return ExecutionResult(
                success=False,
                exit_code=-1,
                stdout="",
                stderr="Execution timed out",
                duration_ms=context.timeout * 1000,
                resource_stats={"timeout_triggered": True}
            )
        except Exception as e:
            if binary_path.exists():
                binary_path.unlink()
            return ExecutionResult(
                success=False,
                exit_code=-1,
                stdout="",
                stderr=str(e),
                duration_ms=(time.time() - compile_start) * 1000,
                resource_stats={"error": str(e)}
            )
