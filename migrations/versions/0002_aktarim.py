"""aktarim: isim anahtari, kaynak dis kimligi, kaynak durumlari

Revision ID: 0002_aktarim
Revises: 0001_ilk_sema
"""
from alembic import op
import sqlalchemy as sa

from app.text import katla


revision = '0002_aktarim'
down_revision = '0001_ilk_sema'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Önce boş değerle eklenir, mevcut satırlar doldurulur, sonra NOT NULL yapılır.
    with op.batch_alter_table('sehitler') as batch_op:
        batch_op.add_column(sa.Column('isim_anahtari', sa.String(length=400), nullable=False, server_default=''))

    sehitler = sa.table(
        'sehitler',
        sa.column('id', sa.Integer),
        sa.column('ad', sa.String),
        sa.column('soyad', sa.String),
        sa.column('lakap', sa.String),
        sa.column('isim_anahtari', sa.String),
    )
    baglanti = op.get_bind()
    for satir in baglanti.execute(sa.select(sehitler.c.id, sehitler.c.ad, sehitler.c.soyad, sehitler.c.lakap)).all():
        anahtar = katla(" ".join([satir.ad, satir.soyad or "", satir.lakap or ""]).strip())[:400]
        baglanti.execute(sehitler.update().where(sehitler.c.id == satir.id).values(isim_anahtari=anahtar))

    with op.batch_alter_table('sehitler') as batch_op:
        batch_op.alter_column('isim_anahtari', existing_type=sa.String(length=400), server_default=None)
        batch_op.create_index(batch_op.f('ix_sehitler_isim_anahtari'), ['isim_anahtari'], unique=False)

    with op.batch_alter_table('sehitler') as batch_op:
        batch_op.add_column(sa.Column('elle_duzenlendi', sa.Boolean(), nullable=False, server_default=sa.false()))

    with op.batch_alter_table('kaynaklar') as batch_op:
        batch_op.add_column(sa.Column('kaynak_kodu', sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column('dis_kimlik', sa.String(length=300), nullable=True))
        batch_op.create_unique_constraint('uq_kaynak_dis_kimlik', ['kaynak_kodu', 'dis_kimlik'])

    op.create_table('kaynak_durumlari',
    sa.Column('kaynak_kodu', sa.String(length=50), nullable=False),
    sa.Column('imlec', sa.String(length=300), nullable=True),
    sa.Column('tamamlandi', sa.Boolean(), nullable=False),
    sa.Column('son_calisma', sa.DateTime(timezone=True), nullable=True),
    sa.Column('son_durum', sa.String(length=20), nullable=True),
    sa.Column('son_mesaj', sa.Text(), nullable=True),
    sa.Column('eklenen', sa.Integer(), nullable=False),
    sa.Column('birlesen', sa.Integer(), nullable=False),
    sa.Column('atlanan', sa.Integer(), nullable=False),
    sa.Column('hatali', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('kaynak_kodu')
    )


def downgrade() -> None:
    op.drop_table('kaynak_durumlari')
    with op.batch_alter_table('kaynaklar') as batch_op:
        batch_op.drop_constraint('uq_kaynak_dis_kimlik', type_='unique')
        batch_op.drop_column('dis_kimlik')
        batch_op.drop_column('kaynak_kodu')
    with op.batch_alter_table('sehitler') as batch_op:
        batch_op.drop_column('elle_duzenlendi')
        batch_op.drop_index(batch_op.f('ix_sehitler_isim_anahtari'))
        batch_op.drop_column('isim_anahtari')
