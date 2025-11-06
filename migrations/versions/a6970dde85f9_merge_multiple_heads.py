"""Merge multiple heads

Revision ID: a6970dde85f9
Revises: 758cf87e1503, 9f17df3a5b20, c8b2888c53fb, e3b2c7a9f1ab
Create Date: 2025-11-06 10:36:27.229363

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a6970dde85f9'
down_revision = ('758cf87e1503', '9f17df3a5b20', 'c8b2888c53fb', 'e3b2c7a9f1ab')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
