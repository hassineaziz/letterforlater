"""create_blog_post_table (idempotent)

Revision ID: daaddb3c1e00
Revises: 1c8cbc0ff441
Create Date: 2025-11-06 10:35:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = 'daaddb3c1e00'
down_revision = '1c8cbc0ff441'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table('blog_post'):
        op.create_table(
            'blog_post',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('slug', sa.String(length=200), nullable=False, unique=True),
            sa.Column('title', sa.String(length=200), nullable=False),
            sa.Column('excerpt', sa.String(length=300), nullable=True),
            sa.Column('content_html', sa.Text(), nullable=False),
            sa.Column('cover_image_url', sa.String(length=500), nullable=True),
            sa.Column('status', sa.String(length=20), nullable=True, server_default='draft'),
            sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('author_id', sa.Integer(), sa.ForeignKey('user.id', ondelete='SET NULL'), nullable=True),
            sa.Column('tags', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column('meta_title', sa.String(length=255), nullable=True),
            sa.Column('meta_description', sa.String(length=255), nullable=True),
            sa.Column('focus_keyword', sa.String(length=100), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=True),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=True),
        )

    # Create indexes if missing
    existing_indexes = {ix['name'] for ix in inspector.get_indexes('blog_post')} if inspector.has_table('blog_post') else set()
    if 'idx_blog_status_published_at' not in existing_indexes and inspector.has_table('blog_post'):
        op.create_index('idx_blog_status_published_at', 'blog_post', ['status', 'published_at'])
    if 'idx_blog_slug' not in existing_indexes and inspector.has_table('blog_post'):
        op.create_index('idx_blog_slug', 'blog_post', ['slug'])
    if 'idx_blog_tags' not in existing_indexes and inspector.has_table('blog_post'):
        op.create_index('idx_blog_tags', 'blog_post', ['tags'], postgresql_using='gin')


def downgrade():
    # Safe downgrade: drop indexes then table if exists
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table('blog_post'):
        existing_indexes = {ix['name'] for ix in inspector.get_indexes('blog_post')}
        for name in ('idx_blog_tags', 'idx_blog_slug', 'idx_blog_status_published_at'):
            if name in existing_indexes:
                op.drop_index(name, table_name='blog_post')
        op.drop_table('blog_post')


