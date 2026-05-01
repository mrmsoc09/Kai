"""
REST API for the Advanced Scripting Orchestrator.
"""
from typing import List, Optional, Dict, Any
from datetime import datetime
from contextlib import contextmanager

from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .models import (
    init_database, get_session_factory, ScriptLanguage, 
    ScriptStatus, ExecutionStatus
)
from .repository import ScriptRepository
from .executor import ExecutionEngine
from .scheduler import TaskScheduler
from .ai_generator import ScriptGenerator, GenerationRequest
from .config import config


# Initialize FastAPI app
app = FastAPI(
    title="Advanced Scripting Orchestrator",
    description="API for managing, generating, and executing security and automation scripts",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global state
engine = None
SessionLocal = None
execution_engine = ExecutionEngine()
scheduler = None
generator = None


# Pydantic models
class ScriptCreate(BaseModel):
    name: str
    content: str
    language: ScriptLanguage
    description: str = ""
    author: str = ""
    tags: List[str] = []
    metadata: Dict[str, Any] = {}


class ScriptUpdate(BaseModel):
    content: Optional[str] = None
    description: Optional[str] = None
    status: Optional[ScriptStatus] = None
    tags: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None


class ScriptResponse(BaseModel):
    id: int
    name: str
    description: str
    language: ScriptLanguage
    version: str
    status: ScriptStatus
    author: str
    tags: List[str]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class ExecutionRequest(BaseModel):
    arguments: List[str] = []
    environment: Dict[str, str] = {}


class ExecutionResponse(BaseModel):
    id: int
    script_id: int
    status: ExecutionStatus
    output: Optional[str]
    error_output: Optional[str]
    exit_code: Optional[int]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    
    class Config:
        from_attributes = True


class ScheduleCreate(BaseModel):
    script_id: int
    cron_expression: str
    timezone: str = "UTC"
    parameters: Dict[str, Any] = {}


class DependencyCreate(BaseModel):
    script_id: int
    depends_on_id: int


class GenerateRequest(BaseModel):
    description: str
    language: ScriptLanguage
    requirements: List[str] = []
    security_level: str = "strict"


# Dependency injection
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.on_event("startup")
async def startup_event():
    global engine, SessionLocal, scheduler, generator
    engine = init_database(config.db.url)
    SessionLocal = get_session_factory(engine)
    
    generator = ScriptGenerator(config.ai.api_key, config.ai.model_name)
    
    # Start scheduler in background
    scheduler = TaskScheduler(execution_engine, SessionLocal)
    asyncio.create_task(scheduler.start_scheduler())


@app.on_event("shutdown")
async def shutdown_event():
    if scheduler:
        scheduler.stop_scheduler()


# Script endpoints
@app.post("/scripts", response_model=ScriptResponse)
def create_script(script: ScriptCreate, db: Session = Depends(get_db)):
    repo = ScriptRepository(db)
    
    # Check for duplicate name
    existing = repo.get_script_by_name(script.name)
    if existing:
        raise HTTPException(status_code=400, detail="Script with this name already exists")
    
    new_script = repo.create_script(
        name=script.name,
        content=script.content,
        language=script.language,
        description=script.description,
        author=script.author,
        tags=script.tags,
        metadata=script.metadata
    )
    return new_script


@app.get("/scripts", response_model=List[ScriptResponse])
def list_scripts(
    language: Optional[ScriptLanguage] = None,
    tags: Optional[List[str]] = Query(None),
    status: Optional[ScriptStatus] = None,
    db: Session = Depends(get_db)
):
    repo = ScriptRepository(db)
    scripts = repo.list_scripts(language=language, tags=tags, status=status)
    return scripts


@app.get("/scripts/{script_id}", response_model=ScriptResponse)
def get_script(script_id: int, db: Session = Depends(get_db)):
    repo = ScriptRepository(db)
    script = repo.get_script(script_id)
    if not script:
        raise HTTPException(status_code=404, detail="Script not found")
    return script


@app.put("/scripts/{script_id}", response_model=ScriptResponse)
def update_script(script_id: int, update: ScriptUpdate, db: Session = Depends(get_db)):
    repo = ScriptRepository(db)
    script = repo.update_script(
        script_id=script_id,
        content=update.content,
        description=update.description,
        status=update.status,
        tags=update.tags,
        metadata=update.metadata
    )
    if not script:
        raise HTTPException(status_code=404, detail="Script not found")
    return script


@app.delete("/scripts/{script_id}")
def delete_script(script_id: int, db: Session = Depends(get_db)):
    repo = ScriptRepository(db)
    if not repo.delete_script(script_id):
        raise HTTPException(status_code=404, detail="Script not found")
    return {"message": "Script deleted"}


# Execution endpoints
@app.post("/scripts/{script_id}/execute", response_model=ExecutionResponse)
async def execute_script(
    script_id: int,
    request: ExecutionRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    repo = ScriptRepository(db)
    script = repo.get_script(script_id)
    if not script:
        raise HTTPException(status_code=404, detail="Script not found")
    
    execution = await execution_engine.execute_script(
        script=script,
        session=db,
        arguments=request.arguments,
        environment=request.environment,
        triggered_by="api"
    )
    return execution


@app.get("/executions", response_model=List[ExecutionResponse])
def list_executions(
    script_id: Optional[int] = None,
    status: Optional[ExecutionStatus] = None,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    repo = ScriptRepository(db)
    return repo.get_execution_history(script_id=script_id, status=status, limit=limit)


# Workflow/Dependency endpoints
@app.post("/workflows/execute")
async def execute_workflow(
    script_ids: List[int],
    db: Session = Depends(get_db)
):
    """Execute multiple scripts respecting dependencies."""
    results = await scheduler.run_workflow(script_ids)
    return {
        "executions": {str(k): v.status for k, v in results.items()},
        "order": list(results.keys())
    }


@app.post("/dependencies")
def add_dependency(dep: DependencyCreate, db: Session = Depends(get_db)):
    try:
        scheduler.add_dependency(dep.script_id, dep.depends_on_id, db)
        return {"message": "Dependency added"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# Scheduling endpoints
@app.post("/schedules")
def create_schedule(schedule: ScheduleCreate, db: Session = Depends(get_db)):
    from .models import Schedule
    
    # Validate script exists
    repo = ScriptRepository(db)
    if not repo.get_script(schedule.script_id):
        raise HTTPException(status_code=404, detail="Script not found")
    
    # Calculate next run
    next_run = scheduler.calculate_next_run(schedule.cron_expression, schedule.timezone)
    
    new_schedule = Schedule(
        script_id=schedule.script_id,
        cron_expression=schedule.cron_expression,
        timezone=schedule.timezone,
        next_run=next_run,
        parameters=schedule.parameters
    )
    db.add(new_schedule)
    db.commit()
    return {"id": new_schedule.id, "next_run": next_run}


# AI Generation endpoints
@app.post("/generate")
async def generate_script(request: GenerateRequest):
    if not generator:
        raise HTTPException(status_code=503, detail="AI generator not configured")
    
    gen_request = GenerationRequest(
        description=request.description,
        language=request.language,
        requirements=request.requirements,
        security_level=request.security_level
    )
    
    try:
        code, explanation, metadata = await generator.generate_script(gen_request)
        return {
            "code": code,
            "explanation": explanation,
            "metadata": metadata
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/analyze/{script_id}")
async def analyze_script(script_id: int, db: Session = Depends(get_db)):
    """Analyze existing script with AI."""
    if not generator:
        raise HTTPException(status_code=503, detail="AI generator not configured")
    
    repo = ScriptRepository(db)
    script = repo.get_script(script_id)
    if not script:
        raise HTTPException(status_code=404, detail="Script not found")
    
    analysis = await generator.analyze_script(script.content, script.language)
    return analysis


# System endpoints
@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "scheduler_running": scheduler.running if scheduler else False,
        "resources": execution_engine.get_system_resources()
    }


import asyncio
