"""webhooklar: yeni şehit duyuruları için webhook kayıtları

Revision ID: 0005_webhooklar
Revises: 0004_sehadet_ayrintisi
"""
from alembic import op
import sqlalchemy as sa


revision = '0005_webhooklar'
down_revision = '0004_sehadet_ayrintisi'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'webhooklar',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('url', sa.Text(), nullable=False),
        sa.Column('tur', sa.Enum('discord', 'genel', name='webhookturu', native_enum=False, length=20), nullable=False),
        sa.Column('ad', sa.String(length=100), nullable=True),
        sa.Column('iletisim', sa.String(length=200), nullable=True),
        sa.Column('durum', sa.Enum('onay_bekliyor', 'aktif', 'kapali', 'reddedildi', name='webhookdurumu',
                                   native_enum=False, length=20), nullable=False),
        sa.Column('silme_anahtari_ozeti', sa.String(length=64), nullable=False),
        sa.Column('imza_anahtari', sa.String(length=64), nullable=False),
        sa.Column('olusturma', sa.DateTime(timezone=True), nullable=False),
        sa.Column('son_gonderim', sa.DateTime(timezone=True), nullable=True),
        sa.Column('son_sonuc', sa.String(length=300), nullable=True),
        sa.Column('ardisik_hata', sa.Integer(), nullable=False),
        sa.Column('gonderim_sayisi', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('url'),
    )
    op.create_index('ix_webhooklar_durum', 'webhooklar', ['durum'], unique=False)
    with op.batch_alter_table('sehitler') as batch_op:
        batch_op.add_column(sa.Column('webhook_duyurusu', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('sehitler') as batch_op:
        batch_op.drop_column('webhook_duyurusu')
    op.drop_index('ix_webhooklar_durum', table_name='webhooklar')
    op.drop_table('webhooklar')
