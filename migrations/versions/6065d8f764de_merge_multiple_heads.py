"""Merge multiple heads

Revision ID: 6065d8f764de
Revises: 1c8cbc0ff441, cf9d2ffe2ad3
Create Date: 2025-10-15 15:53:43.558470

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '6065d8f764de'
down_revision = ('1c8cbc0ff441', 'cf9d2ffe2ad3')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
