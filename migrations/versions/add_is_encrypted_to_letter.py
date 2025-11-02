"""add is_encrypted to letter

Revision ID: add_is_encrypted
Revises: 4e5ddfb95026
Create Date: 2025-01-XX XX:XX:XX.XXXXXX

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_is_encrypted'
down_revision = '4e5ddfb95026'  # Directly depends on merge migration (is_send_to_myself already exists)
branch_labels = None
depends_on = None


def upgrade():
    # Add is_encrypted column to letter table
    op.add_column('letter', sa.Column('is_encrypted', sa.Boolean(), nullable=False, server_default='false'))


def downgrade():
    # Remove is_encrypted column from letter table
    op.drop_column('letter', 'is_encrypted')

