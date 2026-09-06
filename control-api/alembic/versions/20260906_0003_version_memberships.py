"""Add deployment version identity to route memberships.

Revision ID: 20260906_0003
Revises: 20260802_0002
Create Date: 2026-09-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260906_0003"
down_revision: str | None = "20260802_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("route_memberships", sa.Column("version_id", sa.Uuid(), nullable=True))
    op.execute(
        sa.text(
            """
            UPDATE route_memberships AS membership
            SET version_id = backend.version_id
            FROM backend_instances AS backend
            WHERE membership.instance_id = backend.id
            """
        )
    )
    op.alter_column("route_memberships", "version_id", nullable=False)
    op.create_foreign_key(
        "fk_route_memberships_version_id",
        "route_memberships",
        "deployment_versions",
        ["version_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint("fk_route_memberships_version_id", "route_memberships", type_="foreignkey")
    op.drop_column("route_memberships", "version_id")
