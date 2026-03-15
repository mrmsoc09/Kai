"""Add missing indexes for Program and Finding models

Revision ID: task_42_indexes
Revises: 
Create Date: 2026-03-15 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'task_42_indexes'
down_revision = '0011_phase10_5_specialized_agent_framework'
branch_labels = None
depends_on = None


def upgrade():
    # Program indexes
    op.create_index('ix_programs_program_key', 'programs', ['program_key'], unique=False)
    op.create_index('ix_programs_created_by', 'programs', ['created_by'], unique=False)
    
    # Finding indexes
    op.create_index('ix_findings_program_status', 'findings', ['program', 'status'], unique=False)
    op.create_index('ix_findings_severity', 'findings', ['severity'], unique=False)
    op.create_index('ix_findings_asset', 'findings', ['asset'], unique=False)


def downgrade():
    op.drop_index('ix_findings_asset', table_name='findings')
    op.drop_index('ix_findings_severity', table_name='findings')
    op.drop_index('ix_findings_program_status', table_name='findings')
    op.drop_index('ix_programs_created_by', table_name='programs')
    op.drop_index('ix_programs_program_key', table_name='programs')
