"""add is_send_to_myself to letter

Revision ID: add_is_send_to_myself
Revises: 
Create Date: 2025-01-XX XX:XX:XX.XXXXXX

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_is_send_to_myself'
down_revision = '4e5ddfb95026'  # Based on merge migration
branch_labels = None
depends_on = None


def upgrade():
    # Add is_send_to_myself column to letter table (only if it doesn't exist)
    # Check if column already exists using PostgreSQL information_schema
    from sqlalchemy import text
    conn = op.get_bind()
    result = conn.execute(text("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name='letter' AND column_name='is_send_to_myself'
    """))
    column_exists = result.fetchone() is not None
    
    if not column_exists:
        op.add_column('letter', sa.Column('is_send_to_myself', sa.Boolean(), nullable=False, server_default='false'))


def downgrade():
    # Remove is_send_to_myself column from letter table
    op.drop_column('letter', 'is_send_to_myself')

