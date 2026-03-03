"""add username to users

Revision ID: 0002_add_username
Revises: 0001_initial
Create Date: 2026-03-01
"""

from alembic import op
import sqlalchemy as sa


revision = "0002_add_username"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("username", sa.String(length=64), nullable=True))
    op.create_index("ix_users_username", "users", ["username"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_users_username", table_name="users")
    op.drop_column("users", "username")
