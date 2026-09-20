"""Store the provisioned LAB fault kind separately from its scenario name."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260920_0003"
down_revision: str | None = "20260802_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("lab_faults", sa.Column("scenario_kind", sa.String(24), nullable=True))
    op.execute(
        sa.text(
            """
            UPDATE lab_faults
            SET scenario_kind = CASE scenario
                WHEN 'CHECKOUT_INST_B_FAILURE' THEN 'route_failure'
                WHEN 'AUTH_INST_A_FAILURE' THEN 'route_failure'
                WHEN 'GRAY_FAILURE_INST_A' THEN 'gray_failure'
                WHEN 'INST_B_DOWN' THEN 'instance_down'
                WHEN 'SHARED_CHECKOUT_FAILURE' THEN 'route_failure'
                WHEN 'UNKNOWN_CONFLICT' THEN 'unknown_conflict'
                ELSE NULL
            END
            """
        )
    )


def downgrade() -> None:
    op.drop_column("lab_faults", "scenario_kind")