"""
Database models for script repository, metadata, and execution tracking.
"""
from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any
from sqlalchemy import (
    create_engine, Column, Integer, String, Text, DateTime, 
    ForeignKey, Table, Float, Boolean, JSON, Enum as SQLEnum
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker

Base = declarative_base()


# Association table for many-to-many relationship between scripts and tags
script_tags = Table(
    'script_tags',
    Base.metadata,
    Column('script_id', Integer, ForeignKey('scripts.id'), primary_key=True),
    Column('tag_id', Integer, ForeignKey('tags.id'), primary_key=True)
)


class ScriptLanguage(str, Enum):
    PYTHON = "python"
    BASH = "bash"
    GO = "go"


class ScriptStatus(str, Enum):
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    DRAFT = "draft"


class ExecutionStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


class Script(Base):
    __tablename__ = 'scripts'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text)
    content = Column(Text, nullable=False)
    language = Column(SQLEnum(ScriptLanguage), nullable=False)
    version = Column(String(50), default="1.0.0")
    status = Column(SQLEnum(ScriptStatus), default=ScriptStatus.DRAFT)
    author = Column(String(100))
    metadata_json = Column(JSON, default=dict)  # Stores requirements, env vars, etc.
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    tags = relationship("Tag", secondary=script_tags, back_populates="scripts")
    executions = relationship("Execution", back_populates="script", cascade="all, delete-orphan")
    dependencies = relationship(
        "TaskDependency", 
        foreign_keys="TaskDependency.script_id",
        back_populates="script"
    )
    dependents = relationship(
        "TaskDependency",
        foreign_keys="TaskDependency.depends_on_id",
        back_populates="depends_on"
    )
    schedules = relationship("Schedule", back_populates="script", cascade="all, delete-orphan")


class Tag(Base):
    __tablename__ = 'tags'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(50), unique=True, nullable=False, index=True)
    description = Column(String(255))
    category = Column(String(50))  # e.g., "security", "automation", "maintenance"
    
    scripts = relationship("Script", secondary=script_tags, back_populates="tags")


class Execution(Base):
    __tablename__ = 'executions'
    
    id = Column(Integer, primary_key=True)
    script_id = Column(Integer, ForeignKey('scripts.id'), nullable=False)
    status = Column(SQLEnum(ExecutionStatus), default=ExecutionStatus.PENDING)
    output = Column(Text)
    error_output = Column(Text)
    exit_code = Column(Integer)
    resource_usage = Column(JSON)  # CPU, memory, IO stats
    triggered_by = Column(String(100))  # user, scheduler, api, etc.
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    execution_context = Column(JSON)  # Environment variables, arguments, etc.
    
    script = relationship("Script", back_populates="executions")


class TaskDependency(Base):
    __tablename__ = 'task_dependencies'
    
    id = Column(Integer, primary_key=True)
    script_id = Column(Integer, ForeignKey('scripts.id'), nullable=False)
    depends_on_id = Column(Integer, ForeignKey('scripts.id'), nullable=False)
    dependency_type = Column(String(20), default="hard")  # hard, soft
    condition = Column(String(255))  # Optional condition expression
    
    script = relationship("Script", foreign_keys=[script_id], back_populates="dependencies")
    depends_on = relationship("Script", foreign_keys=[depends_on_id], back_populates="dependents")


class Schedule(Base):
    __tablename__ = 'schedules'
    
    id = Column(Integer, primary_key=True)
    script_id = Column(Integer, ForeignKey('scripts.id'), nullable=False)
    cron_expression = Column(String(100), nullable=False)
    timezone = Column(String(50), default="UTC")
    is_active = Column(Boolean, default=True)
    next_run = Column(DateTime)
    last_run = Column(DateTime)
    max_retries = Column(Integer, default=3)
    retry_count = Column(Integer, default=0)
    parameters = Column(JSON)  # Parameters to pass to script
    
    script = relationship("Script", back_populates="schedules")


def init_database(db_url: str = "sqlite:///orchestrator.db"):
    """Initialize database tables."""
    engine = create_engine(db_url)
    Base.metadata.create_all(engine)
    return engine


def get_session_factory(engine):
    return sessionmaker(bind=engine)
