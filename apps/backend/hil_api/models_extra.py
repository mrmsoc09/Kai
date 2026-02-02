from sqlalchemy.orm import relationship
from sqlalchemy import Column, Text, TIMESTAMP, func
from sqlalchemy.dialects.postgresql import ARRAY
from .models import Base

class ProgramScope(Base):
    __tablename__ = 'program_scopes'
    program = Column(Text, primary_key=True)
    allowed_assets = Column(ARRAY(Text))
    excluded_assets = Column(ARRAY(Text))
    allowed_domains = Column(ARRAY(Text))
    excluded_domains = Column(ARRAY(Text))
    min_severity = Column(Text, nullable=True)
    notes = Column(Text)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
