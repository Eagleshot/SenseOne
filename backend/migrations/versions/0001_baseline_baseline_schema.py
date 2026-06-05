"""baseline schema

Revision ID: 0001_baseline
Revises:
Create Date: 2026-06-05 15:51:03.415119

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0001_baseline'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('users',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('email', sa.Text(), nullable=False),
    sa.Column('password_hash', sa.Text(), nullable=False),
    sa.Column('is_platform_admin', sa.Boolean(), nullable=False),
    sa.Column('plan', sa.Text(), server_default='free', nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('email')
    )
    op.create_table('stations',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('public_id', sa.Text(), nullable=False),
    sa.Column('url_slug', sa.Text(), nullable=False),
    sa.Column('owner_id', sa.Uuid(), nullable=False),
    sa.Column('title', sa.Text(), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('location', sa.Text(), nullable=False),
    sa.Column('country', sa.Text(), nullable=False),
    sa.Column('country_emoji', sa.Text(), nullable=False),
    sa.Column('lat', sa.Double(), nullable=False),
    sa.Column('lon', sa.Double(), nullable=False),
    sa.Column('alt', sa.Double(), nullable=False),
    sa.Column('is_public', sa.Boolean(), nullable=False),
    sa.Column('station_start_time', sa.String(length=5), nullable=False),
    sa.Column('station_stop_time', sa.String(length=5), nullable=False),
    sa.Column('use_sunrise_sunset', sa.Boolean(), nullable=False),
    sa.Column('capture_interval_minutes', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('public_id'),
    sa.UniqueConstraint('url_slug')
    )
    with op.batch_alter_table('stations', schema=None) as batch_op:
        batch_op.create_index('idx_stations_owner', ['owner_id'], unique=False)

    op.create_table('sensor_readings',
    sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), autoincrement=True, nullable=False),
    sa.Column('station_id', sa.Uuid(), nullable=False),
    sa.Column('recorded_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('next_online', sa.DateTime(timezone=True), nullable=True),
    sa.Column('firmware_version', sa.Text(), nullable=True),
    sa.Column('wake_reason', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['station_id'], ['stations.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('sensor_readings', schema=None) as batch_op:
        batch_op.create_index('idx_readings_station_recorded', ['station_id', sa.literal_column('recorded_at DESC')], unique=False)

    op.create_table('datastreams',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('station_id', sa.Uuid(), nullable=False),
    sa.Column('metric', sa.Text(), nullable=False),
    sa.Column('channel', sa.Text(), nullable=False),
    sa.Column('unit', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.ForeignKeyConstraint(['station_id'], ['stations.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('datastreams', schema=None) as batch_op:
        batch_op.create_index('uq_datastreams_station_metric_channel', ['station_id', 'metric', 'channel'], unique=True)

    op.create_table('observations',
    sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), autoincrement=True, nullable=False),
    sa.Column('datastream_id', sa.Uuid(), nullable=False),
    sa.Column('reading_id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), nullable=False),
    sa.Column('recorded_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('value', sa.Double(), nullable=False),
    sa.Column('quality_flag', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['datastream_id'], ['datastreams.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['reading_id'], ['sensor_readings.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('observations', schema=None) as batch_op:
        batch_op.create_index('idx_observations_datastream_recorded', ['datastream_id', sa.literal_column('recorded_at DESC')], unique=False)

    op.create_table('station_device_secrets',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('station_id', sa.Uuid(), nullable=False),
    sa.Column('secret_enc', sa.LargeBinary(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['station_id'], ['stations.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('station_device_secrets', schema=None) as batch_op:
        batch_op.create_index('idx_device_secrets_station', ['station_id'], unique=False)

    op.create_table('station_images',
    sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), autoincrement=True, nullable=False),
    sa.Column('station_id', sa.Uuid(), nullable=False),
    sa.Column('filename', sa.Text(), nullable=False),
    sa.Column('stream', sa.Text(), nullable=True),
    sa.Column('content_type', sa.Text(), nullable=True),
    sa.Column('size_bytes', sa.BigInteger(), nullable=False),
    sa.Column('captured_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('next_online', sa.DateTime(timezone=True), nullable=True),
    sa.Column('storage_key', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.ForeignKeyConstraint(['station_id'], ['stations.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('station_images', schema=None) as batch_op:
        batch_op.create_index('idx_images_station_captured', ['station_id', sa.literal_column('captured_at DESC')], unique=False)
        batch_op.create_index('uq_images_station_filename', ['station_id', 'filename'], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('station_images', schema=None) as batch_op:
        batch_op.drop_index('uq_images_station_filename')
        batch_op.drop_index('idx_images_station_captured')

    op.drop_table('station_images')
    with op.batch_alter_table('station_device_secrets', schema=None) as batch_op:
        batch_op.drop_index('idx_device_secrets_station')

    op.drop_table('station_device_secrets')
    with op.batch_alter_table('observations', schema=None) as batch_op:
        batch_op.drop_index('idx_observations_datastream_recorded')

    op.drop_table('observations')
    with op.batch_alter_table('datastreams', schema=None) as batch_op:
        batch_op.drop_index('uq_datastreams_station_metric_channel')

    op.drop_table('datastreams')
    with op.batch_alter_table('sensor_readings', schema=None) as batch_op:
        batch_op.drop_index('idx_readings_station_recorded')

    op.drop_table('sensor_readings')
    with op.batch_alter_table('stations', schema=None) as batch_op:
        batch_op.drop_index('idx_stations_owner')

    op.drop_table('stations')
    op.drop_table('users')
