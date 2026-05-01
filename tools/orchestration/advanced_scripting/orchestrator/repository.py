"""
Script repository management with metadata and tagging.
"""
from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func

from .models import Script, Tag, ScriptLanguage, ScriptStatus, Execution


class ScriptRepository:
    """Repository for script CRUD operations."""
    
    def __init__(self, session: Session):
        self.session = session
    
    def create_script(
        self,
        name: str,
        content: str,
        language: ScriptLanguage,
        description: str = "",
        author: str = "",
        tags: List[str] = None,
        metadata: Dict[str, Any] = None,
        status: ScriptStatus = ScriptStatus.DRAFT
    ) -> Script:
        """Create new script with tags."""
        script = Script(
            name=name,
            content=content,
            language=language,
            description=description,
            author=author,
            metadata_json=metadata or {},
            status=status
        )
        
        if tags:
            for tag_name in tags:
                tag = self._get_or_create_tag(tag_name)
                script.tags.append(tag)
        
        self.session.add(script)
        self.session.commit()
        return script
    
    def get_script(self, script_id: int) -> Optional[Script]:
        """Get script by ID with tags."""
        return self.session.query(Script).options(
            joinedload(Script.tags)
        ).filter(Script.id == script_id).first()
    
    def get_script_by_name(self, name: str) -> Optional[Script]:
        """Get script by name."""
        return self.session.query(Script).filter(
            func.lower(Script.name) == func.lower(name)
        ).first()
    
    def list_scripts(
        self,
        language: Optional[ScriptLanguage] = None,
        tags: List[str] = None,
        status: Optional[ScriptStatus] = None,
        author: Optional[str] = None
    ) -> List[Script]:
        """List scripts with filters."""
        query = self.session.query(Script).options(joinedload(Script.tags))
        
        if language:
            query = query.filter(Script.language == language)
        if status:
            query = query.filter(Script.status == status)
        if author:
            query = query.filter(Script.author == author)
        if tags:
            query = query.join(Script.tags).filter(Tag.name.in_(tags))
        
        return query.all()
    
    def update_script(
        self,
        script_id: int,
        content: Optional[str] = None,
        description: Optional[str] = None,
        status: Optional[ScriptStatus] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[Script]:
        """Update script fields."""
        script = self.get_script(script_id)
        if not script:
            return None
        
        if content is not None:
            script.content = content
            # Increment version
            parts = script.version.split('.')
            if len(parts) == 3:
                parts[2] = str(int(parts[2]) + 1)
                script.version = '.'.join(parts)
        
        if description is not None:
            script.description = description
        if status is not None:
            script.status = status
        if metadata is not None:
            script.metadata_json.update(metadata)
        
        if tags is not None:
            script.tags = []
            for tag_name in tags:
                tag = self._get_or_create_tag(tag_name)
                script.tags.append(tag)
        
        script.updated_at = datetime.utcnow()
        self.session.commit()
        return script
    
    def delete_script(self, script_id: int) -> bool:
        """Delete script and its executions."""
        script = self.get_script(script_id)
        if not script:
            return False
        
        self.session.delete(script)
        self.session.commit()
        return True
    
    def get_execution_history(
        self,
        script_id: Optional[int] = None,
        limit: int = 100,
        status: Optional[str] = None
    ) -> List[Execution]:
        """Get execution history."""
        query = self.session.query(Execution)
        
        if script_id:
            query = query.filter(Execution.script_id == script_id)
        if status:
            query = query.filter(Execution.status == status)
        
        return query.order_by(Execution.started_at.desc()).limit(limit).all()
    
    def _get_or_create_tag(self, name: str) -> Tag:
        """Get existing tag or create new one."""
        tag = self.session.query(Tag).filter(Tag.name == name).first()
        if not tag:
            tag = Tag(name=name)
            self.session.add(tag)
            self.session.flush()
        return tag
    
    def search_scripts(self, query: str) -> List[Script]:
        """Search scripts by name or description."""
        search = f"%{query}%"
        return self.session.query(Script).filter(
            (Script.name.ilike(search)) | 
            (Script.description.ilike(search))
        ).all()
