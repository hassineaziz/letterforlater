"""Merge multiple heads

Revision ID: 4e5ddfb95026
Revises: 6065d8f764de, a56f6763aeaf
Create Date: 2025-10-18 10:04:13.390565

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4e5ddfb95026'
down_revision = ('6065d8f764de', 'a56f6763aeaf')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
