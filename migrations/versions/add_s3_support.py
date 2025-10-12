"""Add S3 support to MediaAttachment model

Revision ID: add_s3_support
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_s3_support'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Add S3 support columns to MediaAttachment table
    op.add_column('media_attachment', sa.Column('is_s3_stored', sa.Boolean(), nullable=True, default=True))
    op.add_column('media_attachment', sa.Column('s3_bucket', sa.String(length=100), nullable=True))
    op.add_column('media_attachment', sa.Column('s3_etag', sa.String(length=100), nullable=True))
    
    # Set default value for existing records
    op.execute("UPDATE media_attachment SET is_s3_stored = false WHERE is_s3_stored IS NULL")


def downgrade():
    # Remove S3 support columns
    op.drop_column('media_attachment', 's3_etag')
    op.drop_column('media_attachment', 's3_bucket')
    op.drop_column('media_attachment', 'is_s3_stored')
