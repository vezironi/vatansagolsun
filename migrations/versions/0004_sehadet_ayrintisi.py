"""sehadet_ayrintisi: şehadet yeri, şehadet olayı ve fotoğraf adresi

Mevcut kayıtlar boş kalır; kaynaklar `aktar <kod> --bastan` ile yeniden okunduğunda
bilinen kayıtların boş alanları doldurulur.

Revision ID: 0004_sehadet_ayrintisi
Revises: 0003_imlec_text
"""
from alembic import op
import sqlalchemy as sa


revision = '0004_sehadet_ayrintisi'
down_revision = '0003_imlec_text'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('sehitler') as batch_op:
        batch_op.add_column(sa.Column('sehadet_yeri', sa.String(length=200), nullable=True))
        batch_op.add_column(sa.Column('sehadet_olayi', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('fotograf_url', sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('sehitler') as batch_op:
        batch_op.drop_column('fotograf_url')
        batch_op.drop_column('sehadet_olayi')
        batch_op.drop_column('sehadet_yeri')
