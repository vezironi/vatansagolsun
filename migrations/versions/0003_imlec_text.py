"""imlec_text: kaynak_durumlari.imlec VARCHAR(300) -> TEXT

Haber imleci (3 günlük işlenmiş kimlik kümesi) 300 karakteri aşar; PostgreSQL'de
commit hata verir. SQLite uzunluğu yok saydığı için testlerde görünmüyordu.

Revision ID: 0003_imlec_text
Revises: 0002_aktarim
"""
from alembic import op
import sqlalchemy as sa


revision = '0003_imlec_text'
down_revision = '0002_aktarim'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('kaynak_durumlari') as batch_op:
        batch_op.alter_column('imlec', existing_type=sa.String(length=300), type_=sa.Text(),
                              existing_nullable=True)


def downgrade() -> None:
    # 300 karakterden uzun imleçler (haber imleci) geri dönüşte sığmaz: silinir; haber
    # kaynakları bir sonraki çalışmada "ilk çalışma" gibi davranır (yalnızca bugünün haberleri).
    kaynak_durumlari = sa.table('kaynak_durumlari', sa.column('imlec', sa.Text))
    op.execute(
        kaynak_durumlari.update()
        .where(sa.func.length(kaynak_durumlari.c.imlec) > 300)
        .values(imlec=None)
    )
    with op.batch_alter_table('kaynak_durumlari') as batch_op:
        batch_op.alter_column('imlec', existing_type=sa.Text(), type_=sa.String(length=300),
                              existing_nullable=True)
