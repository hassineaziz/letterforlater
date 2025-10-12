"""Update MediaAttachment table for production media system

Revision ID: new_media_attachment_schema
Revises: 52780c920460
Create Date: 2025-01-31 16:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'new_media_attachment_schema'
down_revision = '52780c920460'
branch_labels = None
depends_on = None


def upgrade():
    # Add new columns to MediaAttachment table
    op.add_column('media_attachment', sa.Column('user_id', sa.Integer(), nullable=True))
    op.add_column('media_attachment', sa.Column('is_temporary', sa.Boolean(), nullable=True, default=True))
    op.add_column('media_attachment', sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True))
    
    # Create new indexes
    op.create_index('idx_media_user', 'media_attachment', ['user_id'])
    op.create_index('idx_media_temporary', 'media_attachment', ['is_temporary'])
    op.create_index('idx_media_expires', 'media_attachment', ['expires_at'])
    op.create_index('idx_media_user_temporary', 'media_attachment', ['user_id', 'is_temporary'])
    
    # Add foreign key constraint for user_id
    op.create_foreign_key('fk_media_attachment_user_id', 'media_attachment', 'user', ['user_id'], ['id'], ondelete='CASCADE')
    
    # Update existing records to set user_id from letter relationship
    # This assumes existing media attachments have a letter_id
    op.execute("""
        UPDATE media_attachment 
        SET user_id = (
            SELECT user_id 
            FROM letter 
            WHERE letter.id = media_attachment.letter_id
        )
        WHERE user_id IS NULL AND letter_id IS NOT NULL
    """)
    
    # Set is_temporary to False for existing records (they're already attached to letters)
    op.execute("UPDATE media_attachment SET is_temporary = FALSE WHERE letter_id IS NOT NULL")
    
    # Make user_id NOT NULL after populating it
    op.alter_column('media_attachment', 'user_id', nullable=False)


def downgrade():
    # Remove foreign key constraint
    op.drop_constraint('fk_media_attachment_user_id', 'media_attachment', type_='foreignkey')
    
    # Remove indexes
    op.drop_index('idx_media_user_temporary', table_name='media_attachment')
    op.drop_index('idx_media_expires', table_name='media_attachment')
    op.drop_index('idx_media_temporary', table_name='media_attachment')
    op.drop_index('idx_media_user', table_name='media_attachment')
    
    # Remove columns
    op.drop_column('media_attachment', 'expires_at')
    op.drop_column('media_attachment', 'is_temporary')
    op.drop_column('media_attachment', 'user_id')
