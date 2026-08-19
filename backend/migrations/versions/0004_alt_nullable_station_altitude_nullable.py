"""stations.alt nullable: null means altitude unknown

Altitude was NOT NULL DEFAULT 0.0, which made "unknown" indistinguishable from
a genuine sea-level station. Existing rows keep their stored values (0.0 stays
0.0); only stations saved without an altitude store NULL from now on.

Revision ID: 0004_alt_nullable
Revises: 0003_obs_reading_idx
Create Date: 2026-07-21

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = '0004_alt_nullable'
down_revision: Union[str, Sequence[str], None] = '0003_obs_reading_idx'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('stations', schema=None) as batch_op:
        batch_op.alter_column('alt', existing_type=sa.Double(), nullable=True)


def downgrade() -> None:
    """Downgrade schema."""
    # NULL altitudes have no faithful NOT NULL representation; fall back to the
    # old sentinel 0.0 so the constraint can be restored.
    op.execute("UPDATE stations SET alt = 0.0 WHERE alt IS NULL")
    with op.batch_alter_table('stations', schema=None) as batch_op:
        batch_op.alter_column('alt', existing_type=sa.Double(), nullable=False)
