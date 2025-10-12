"""Remove temporary media storage - permanent storage only

Revision ID: remove_temporary_media_storage
Revises: new_media_attachment_schema
Create Date: 2025-01-11 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'remove_temporary_media_storage'
down_revision = 'new_media_attachment_schema'
branch_labels = None
depends_on = None


def upgrade():
    # Remove temporary storage related columns
    op.drop_column('media_attachment', 'is_temporary')
    op.drop_column('media_attachment', 'expires_at')
    
    # Remove temporary storage related indexes
    op.drop_index('idx_media_temporary', 'media_attachment')
    op.drop_index('idx_media_expires', 'media_attachment')
    op.drop_index('idx_media_user_temporary', 'media_attachment')
    
    # Make letter_id NOT NULL (all media must be attached to a letter)
    op.alter_column('media_attachment', 'letter_id', nullable=False)
    
    # Add new index for user+letter combination
    op.create_index('idx_media_user_letter', 'media_attachment', ['user_id', 'letter_id'])


def downgrade():
    # Add back temporary storage columns
    op.add_column('media_attachment', sa.Column('is_temporary', sa.Boolean(), nullable=True, default=True))
    op.add_column('media_attachment', sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True))
    
    # Add back temporary storage indexes
    op.create_index('idx_media_temporary', 'media_attachment', ['is_temporary'])
    op.create_index('idx_media_expires', 'media_attachment', ['expires_at'])
    op.create_index('idx_media_user_temporary', 'media_attachment', ['user_id', 'is_temporary'])
    
    # Make letter_id nullable again
    op.alter_column('media_attachment', 'letter_id', nullable=True)
    
    # Remove the new index
    op.drop_index('idx_media_user_letter', 'media_attachment')
