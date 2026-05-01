"""
Python language handler with virtual environment support.
"""
import subprocess
import sys
import tempfile
import time
import os
import signal
from pathlib import Path
from typing import Optional
import psutil

from .base import BaseLanguageHandler, LanguageContext, ExecutionResult


class PythonHandler(BaseLanguageHandler):
    """Handler for Python scripts with dependency management."""
    
    @property
    def file_extension(self) -> str:
        return ".py"
    
    def validate_syntax(self, content: str) -> tuple[bool, Optional[str]]:
        """Validate Python syntax using compile()."""
        try:
            compile(content, '<string>', 'exec')
            return True, None
        except SyntaxError as e:
            return False, str(e)
    
    def prepare(self, context: LanguageContext) -> bool:
        """Create virtual environment and install dependencies if specified."""
        venv_path = context.working_dir / ".venv"
        
        try:
            # Create virtual environment
            subprocess.run(
                [sys.executable, "-m", "venv", str(venv_path)],
                check=True,
                capture_output=True,
                timeout=60
            )
            
            # Check for requirements in metadata
            req_file = context.working_dir / "requirements.txt"
            if req_file.exists():
                pip_path = venv_path / "bin" / "pip"
                if not pip_path.exists():
                    pip_path = venv_path / "Scripts" / "pip.exe"
                
                subprocess.run(
                    [str(pip_path), "install", "-r", str(req_file)],
                    check=True,
                    capture_output=True,
                    timeout=120
                )
            return True
        except subprocess.CalledProcessError as e:
            print(f"Failed to prepare Python environment: {e}")
            return False
        except subprocess.TimeoutExpired:
            print("Python environment preparation timed out")
            return False
    
    def execute(self, context: LanguageContext) -> ExecutionResult:
        """Execute Python script with resource monitoring."""
        venv_path = context.working_dir / ".venv"
        python_path = venv_path / "bin" / "python"
        if not python_path.exists():
            python_path = venv_path / "Scripts" / "python.exe"
        
        cmd = [str(python_path), str(context.script_path)] + context.arguments
        
        start_time = time.time()
        process = None
        
        try:
            # Start process
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=str(context.working_dir),
                env={**os.environ, **context.environment},
                preexec_fn=self._set_resource_limits(context.memory_limit_mb)
            )
            
            # Monitor resources
            max_memory = 0
            max_cpu = 0.0
            
            try:
                proc = psutil.Process(process.pid)
                
                # Wait for completion with timeout
                stdout, stderr = process.communicate(timeout=context.timeout)
                duration = (time.time() - start_time) * 1000
                
                # Get final stats
                try:
                    memory_info = proc.memory_info()
                    max_memory = memory_info.rss / 1024 / 1024  # MB
                except psutil.NoSuchProcess:
                    pass
                
                return ExecutionResult(
                    success=process.returncode == 0,
                    exit_code=process.returncode,
                    stdout=stdout.decode('utf-8', errors='replace'),
                    stderr=stderr.decode('utf-8', errors='replace'),
                    duration_ms=duration,
                    resource_stats={
                        "max_memory_mb": max_memory,
                        "cpu_percent": max_cpu,
                        "timeout_triggered": False
                    }
                )
                
            except subprocess.TimeoutExpired:
                process.kill()
                stdout, stderr = process.communicate()
                return ExecutionResult(
                    success=False,
                    exit_code=-1,
                    stdout=stdout.decode('utf-8', errors='replace'),
                    stderr=stderr.decode('utf-8', errors='replace') + "\n[TIMEOUT]",
                    duration_ms=context.timeout * 1000,
                    resource_stats={"timeout_triggered": True}
                )
                
        except Exception as e:
            if process:
                process.kill()
            return ExecutionResult(
                success=False,
                exit_code=-1,
                stdout="",
                stderr=str(e),
                duration_ms=(time.time() - start_time) * 1000,
                resource_stats={"error": str(e)}
            )
    
    def _set_resource_limits(self, memory_limit_mb: int):
        """Set resource limits for the process (Unix only)."""
        def limiter():
            import resource
            # Set memory limit
            if memory_limit_mb > 0:
                resource.setrlimit(
                    resource.RLIMIT_AS, 
                    (memory_limit_mb * 1024 * 1024, memory_limit_mb * 1024 * 1024)
                )
        return limiter
    
    def cleanup(self, context: LanguageContext):
        """Remove virtual environment."""
        venv_path = context.working_dir / ".venv"
        if venv_path.exists():
            import shutil
            shutil.rmtree(venv_path)
