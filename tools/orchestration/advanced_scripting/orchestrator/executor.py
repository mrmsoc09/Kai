"""
Standardized execution environment with resource monitoring.
"""
import asyncio
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
import psutil

from .models import Execution, ExecutionStatus, Script, ScriptLanguage
from .security import Sandbox, SecurityValidator
from .languages import get_handler, LanguageContext
from .config import config


class ExecutionEngine:
    """Manages script execution in sandboxed environment."""
    
    def __init__(self):
        self.active_executions: Dict[int, Any] = {}  # execution_id -> process info
        self.validator = SecurityValidator()
    
    async def execute_script(
        self,
        script: Script,
        session,
        arguments: List[str] = None,
        environment: Dict[str, str] = None,
        triggered_by: str = "api"
    ) -> Execution:
        """
        Execute a script with full sandboxing and monitoring.
        """
        # Create execution record
        execution = Execution(
            script_id=script.id,
            status=ExecutionStatus.PENDING,
            triggered_by=triggered_by,
            execution_context={
                "arguments": arguments or [],
                "environment": environment or {},
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        session.add(execution)
        session.commit()
        
        # Security validation
        is_safe, violations = self.validator.validate_script(script.content, script.language)
        if not is_safe:
            execution.status = ExecutionStatus.FAILED
            execution.error_output = f"Security violations found:\n" + "\n".join(violations)
            session.commit()
            return execution
        
        # Syntax validation
        handler = get_handler(script.language)
        is_valid, error = handler.validate_syntax(script.content)
        if not is_valid:
            execution.status = ExecutionStatus.FAILED
            execution.error_output = f"Syntax error: {error}"
            session.commit()
            return execution
        
        # Execute in sandbox
        with Sandbox(config.execution.temp_dir) as sandbox:
            try:
                execution.status = ExecutionStatus.RUNNING
                execution.started_at = datetime.utcnow()
                session.commit()
                
                # Write script to sandbox
                filename = f"script{handler.file_extension}"
                script_path = sandbox.write_script(filename, script.content)
                
                # Write requirements if Python
                if script.language == ScriptLanguage.PYTHON:
                    requirements = script.metadata_json.get("requirements", [])
                    if requirements:
                        req_content = "\n".join(requirements)
                        req_path = sandbox.sandbox_path / "workspace" / "requirements.txt"
                        req_path.write_text(req_content)
                
                # Prepare context
                ctx = LanguageContext(
                    script_path=script_path,
                    working_dir=sandbox.sandbox_path / "workspace",
                    environment=environment or {},
                    arguments=arguments or [],
                    timeout=config.execution.max_execution_time,
                    memory_limit_mb=config.execution.max_memory_mb,
                    cpu_limit_percent=config.execution.max_cpu_percent
                )
                
                # Prepare environment
                if not handler.prepare(ctx):
                    raise Exception("Failed to prepare execution environment")
                
                # Execute (run in thread pool to not block)
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    None, 
                    handler.execute,
                    ctx
                )
                
                # Update execution record
                execution.status = ExecutionStatus.SUCCESS if result.success else ExecutionStatus.FAILED
                execution.exit_code = result.exit_code
                execution.output = result.stdout
                execution.error_output = result.stderr
                execution.completed_at = datetime.utcnow()
                execution.resource_usage = {
                    **result.resource_stats,
                    "duration_ms": result.duration_ms,
                    "sandbox_id": sandbox.sandbox_id
                }
                
                session.commit()
                
            except Exception as e:
                execution.status = ExecutionStatus.FAILED
                execution.error_output = str(e)
                execution.completed_at = datetime.utcnow()
                session.commit()
        
        return execution
    
    def cancel_execution(self, execution_id: int) -> bool:
        """Cancel a running execution."""
        if execution_id in self.active_executions:
            proc_info = self.active_executions[execution_id]
            try:
                process = psutil.Process(proc_info['pid'])
                process.terminate()
                return True
            except psutil.NoSuchProcess:
                return False
        return False
    
    def get_system_resources(self) -> Dict[str, Any]:
        """Get current system resource usage."""
        return {
            "cpu_percent": psutil.cpu_percent(interval=1),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_usage": psutil.disk_usage('/').percent,
            "active_executions": len(self.active_executions)
        }
