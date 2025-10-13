"""Merge multiple heads

Revision ID: b9caebc156d5
Revises: add_cooldown_field, add_s3_support, newsletter_subscribers_init, remove_temporary_media_storage
Create Date: 2025-10-13 17:37:58.392177

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b9caebc156d5'
down_revision = ('add_cooldown_field', 'add_s3_support', 'newsletter_subscribers_init', 'remove_temporary_media_storage')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
