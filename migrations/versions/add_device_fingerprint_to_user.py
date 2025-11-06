"""add_device_fingerprint_to_user

Revision ID: add_device_fingerprint
Revises: 
Create Date: 2025-11-06 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_device_fingerprint'
down_revision = 'a6970dde85f9'  # Latest merge migration
branch_labels = None
depends_on = None


def upgrade():
    # Check if column already exists
    from sqlalchemy import inspect
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = [col['name'] for col in inspector.get_columns('user')]
    
    with op.batch_alter_table('user', schema=None) as batch_op:
        if 'device_fingerprint' not in columns:
            batch_op.add_column(sa.Column('device_fingerprint', sa.String(length=64), nullable=True))
            # Create index for faster lookups
            batch_op.create_index('idx_user_device_fingerprint', ['device_fingerprint'])


def downgrade():
    from sqlalchemy import inspect
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = [col['name'] for col in inspector.get_columns('user')]
    
    with op.batch_alter_table('user', schema=None) as batch_op:
        if 'device_fingerprint' in columns:
            batch_op.drop_index('idx_user_device_fingerprint')
            batch_op.drop_column('device_fingerprint')

