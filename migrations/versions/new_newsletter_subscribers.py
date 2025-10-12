from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'newsletter_subscribers_init'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'newsletter_subscriber',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('email', sa.String(length=255), nullable=False, unique=True, index=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pending'),
        sa.Column('source', sa.String(length=100), nullable=True),
        sa.Column('tags', sa.String(length=255), nullable=True),
        sa.Column('double_opt_in_token', sa.String(length=64), nullable=True, unique=True),
        sa.Column('confirmed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('unsubscribed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('provider', sa.String(length=50), nullable=True),
        sa.Column('provider_contact_id', sa.String(length=100), nullable=True),
    )
    op.create_index('idx_newsletter_email', 'newsletter_subscriber', ['email'], unique=True)
    op.create_index('idx_newsletter_status', 'newsletter_subscriber', ['status'])


def downgrade():
    op.drop_index('idx_newsletter_status', table_name='newsletter_subscriber')
    op.drop_index('idx_newsletter_email', table_name='newsletter_subscriber')
    op.drop_table('newsletter_subscriber')


