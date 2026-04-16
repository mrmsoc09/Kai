"""merge_phase1_and_task42_indexes

Revision ID: 02076b75458b
Revises: 0026_phase1_tenant_and_fk, task_42_indexes
Create Date: 2026-04-16 10:46:45.376494

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '02076b75458b'
down_revision = ('0026_phase1_tenant_and_fk', 'task_42_indexes')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
