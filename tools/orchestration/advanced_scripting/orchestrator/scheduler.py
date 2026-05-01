"""
Task dependency management and scheduling using DAG and cron.
"""
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Set, Optional, Any
from dataclasses import dataclass
import heapq
from croniter import croniter

from .models import Script, Schedule, Execution, ExecutionStatus, TaskDependency


class DependencyGraph:
    """Manages task dependencies as a Directed Acyclic Graph (DAG)."""
    
    def __init__(self):
        self.graph: Dict[int, Set[int]] = {}  # script_id -> set of dependencies
        self.reverse_graph: Dict[int, Set[int]] = {}  # script_id -> set of dependents
    
    def add_dependency(self, script_id: int, depends_on: int):
        """Add dependency: script_id depends on depends_on."""
        if script_id not in self.graph:
            self.graph[script_id] = set()
        self.graph[script_id].add(depends_on)
        
        if depends_on not in self.reverse_graph:
            self.reverse_graph[depends_on] = set()
        self.reverse_graph[depends_on].add(script_id)
    
    def remove_dependency(self, script_id: int, depends_on: int):
        """Remove a dependency."""
        if script_id in self.graph:
            self.graph[script_id].discard(depends_on)
        if depends_on in self.reverse_graph:
            self.reverse_graph[depends_on].discard(script_id)
    
    def get_dependencies(self, script_id: int) -> Set[int]:
        """Get all dependencies for a script."""
        return self.graph.get(script_id, set())
    
    def get_dependents(self, script_id: int) -> Set[int]:
        """Get all scripts that depend on this script."""
        return self.reverse_graph.get(script_id, set())
    
    def topological_sort(self, script_ids: List[int]) -> List[int]:
        """
        Return topologically sorted list of scripts.
        Raises ValueError if cycle detected.
        """
        in_degree = {sid: 0 for sid in script_ids}
        adj = {sid: set() for sid in script_ids}
        
        # Build adjacency list for requested scripts only
        for sid in script_ids:
            for dep in self.get_dependencies(sid):
                if dep in script_ids:
                    adj[dep].add(sid)
                    in_degree[sid] += 1
        
        # Kahn's algorithm
        queue = [sid for sid in script_ids if in_degree[sid] == 0]
        result = []
        
        while queue:
            node = queue.pop(0)
            result.append(node)
            
            for neighbor in adj[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
        
        if len(result) != len(script_ids):
            raise ValueError("Circular dependency detected")
        
        return result
    
    def has_cycle(self) -> bool:
        """Check if graph has cycles."""
        visited = set()
        rec_stack = set()
        
        def dfs(node):
            visited.add(node)
            rec_stack.add(node)
            
            for neighbor in self.graph.get(node, set()):
                if neighbor not in visited:
                    if dfs(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True
            
            rec_stack.remove(node)
            return False
        
        for node in list(self.graph.keys()):
            if node not in visited:
                if dfs(node):
                    return True
        return False


class TaskScheduler:
    """Manages scheduled tasks and dependency resolution."""
    
    def __init__(self, execution_engine, session_factory):
        self.execution_engine = execution_engine
        self.session_factory = session_factory
        self.graph = DependencyGraph()
        self.running = False
        self.task_queue = asyncio.PriorityQueue()
        self._load_dependencies()
    
    def _load_dependencies(self):
        """Load existing dependencies from database."""
        session = self.session_factory()
        try:
            deps = session.query(TaskDependency).all()
            for dep in deps:
                self.graph.add_dependency(dep.script_id, dep.depends_on_id)
        finally:
            session.close()
    
    def add_dependency(self, script_id: int, depends_on_id: int, session):
        """Add dependency between scripts."""
        if script_id == depends_on_id:
            raise ValueError("Script cannot depend on itself")
        
        self.graph.add_dependency(script_id, depends_on_id)
        
        if self.graph.has_cycle():
            self.graph.remove_dependency(script_id, depends_on_id)
            raise ValueError("Adding this dependency would create a cycle")
        
        dep = TaskDependency(script_id=script_id, depends_on_id=depends_on_id)
        session.add(dep)
        session.commit()
    
    async def run_workflow(self, script_ids: List[int], triggered_by: str = "scheduler") -> Dict[int, Execution]:
        """
        Execute multiple scripts respecting dependencies.
        """
        session = self.session_factory()
        try:
            # Get topological order
            execution_order = self.graph.topological_sort(script_ids)
            results = {}
            
            for script_id in execution_order:
                # Check if dependencies succeeded
                deps = self.graph.get_dependencies(script_id)
                deps_satisfied = all(
                    results.get(dep_id) and results[dep_id].status == ExecutionStatus.SUCCESS
                    for dep_id in deps if dep_id in script_ids
                )
                
                if not deps_satisfied:
                    # Create failed execution record
                    script = session.query(Script).get(script_id)
                    execution = Execution(
                        script_id=script_id,
                        status=ExecutionStatus.FAILED,
                        error_output="Dependencies not satisfied",
                        triggered_by=triggered_by
                    )
                    session.add(execution)
                    session.commit()
                    results[script_id] = execution
                    continue
                
                # Execute script
                script = session.query(Script).get(script_id)
                execution = await self.execution_engine.execute_script(
                    script, session, triggered_by=triggered_by
                )
                results[script_id] = execution
                
                # If failed and has dependents, stop workflow
                if execution.status != ExecutionStatus.SUCCESS:
                    break
            
            return results
        finally:
            session.close()
    
    async def start_scheduler(self):
        """Start the cron scheduler loop."""
        self.running = True
        while self.running:
            await self._process_schedules()
            await asyncio.sleep(60)  # Check every minute
    
    async def _process_schedules(self):
        """Check and execute due schedules."""
        session = self.session_factory()
        try:
            now = datetime.utcnow()
            schedules = session.query(Schedule).filter(
                Schedule.is_active == True,
                Schedule.next_run <= now
            ).all()
            
            for schedule in schedules:
                # Update next run time
                itr = croniter(schedule.cron_expression, now)
                schedule.next_run = itr.get_next(datetime)
                schedule.last_run = now
                
                # Execute
                script = session.query(Script).get(schedule.script_id)
                await self.execution_engine.execute_script(
                    script,
                    session,
                    arguments=schedule.parameters.get("arguments", []),
                    environment=schedule.parameters.get("environment", {}),
                    triggered_by=f"schedule:{schedule.id}"
                )
            
            session.commit()
        except Exception as e:
            print(f"Scheduler error: {e}")
        finally:
            session.close()
    
    def stop_scheduler(self):
        """Stop the scheduler."""
        self.running = False
    
    def calculate_next_run(self, cron_expr: str, timezone: str = "UTC") -> datetime:
        """Calculate next execution time from cron expression."""
        now = datetime.utcnow()
        itr = croniter(cron_expr, now)
        return itr.get_next(datetime)
