"""merge add_is_send_to_myself and add_is_encrypted

Revision ID: 4c48aba4793d
Revises: add_is_send_to_myself, add_is_encrypted
Create Date: 2025-11-02 10:29:03.827386

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4c48aba4793d'
down_revision = ('add_is_send_to_myself', 'add_is_encrypted')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
