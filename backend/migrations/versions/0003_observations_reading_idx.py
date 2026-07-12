"""index observations.reading_id for FK cascade lookups

Station deletion cascades stations -> sensor_readings -> observations; SQLite
looks up the child observations per deleted reading row, which is a full table
scan per reading without this index.

Revision ID: 0003_obs_reading_idx
Revises: 0002_auth_sessions
Create Date: 2026-06-11

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '0003_obs_reading_idx'
down_revision: Union[str, Sequence[str], None] = '0002_auth_sessions'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('observations', schema=None) as batch_op:
        batch_op.create_index('idx_observations_reading', ['reading_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('observations', schema=None) as batch_op:
        batch_op.drop_index('idx_observations_reading')
