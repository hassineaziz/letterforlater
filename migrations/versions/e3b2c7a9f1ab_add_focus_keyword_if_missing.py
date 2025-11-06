"""add_focus_keyword_if_missing

Revision ID: e3b2c7a9f1ab
Revises: daaddb3c1e00
Create Date: 2025-11-06 10:38:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e3b2c7a9f1ab'
down_revision = 'daaddb3c1e00'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table('blog_post'):
        cols = {c['name'] for c in inspector.get_columns('blog_post')}
        if 'focus_keyword' not in cols:
            with op.batch_alter_table('blog_post') as batch_op:
                batch_op.add_column(sa.Column('focus_keyword', sa.String(length=100), nullable=True))


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table('blog_post'):
        cols = {c['name'] for c in inspector.get_columns('blog_post')}
        if 'focus_keyword' in cols:
            with op.batch_alter_table('blog_post') as batch_op:
                batch_op.drop_column('focus_keyword')


