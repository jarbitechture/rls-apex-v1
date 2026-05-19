"""p1 id_counter table — per-year contiguous RLS number allocation

Revision ID: p1a1b2c3d4e5
Revises: c5f2154f8fb3
Create Date: 2026-05-19

Per DECISION_LOG Lock #23: a per-year counter row, mutated via atomic
INSERT ... ON CONFLICT (year) DO UPDATE ... RETURNING inside the genesis
tx, gives contiguous gap-free official RLS numbers (rollback consumes no
number). Single-row-lock scaling limit documented in the P1 spec §13.
"""
from alembic import op
import sqlalchemy as sa

revision = "p1a1b2c3d4e5"
down_revision = "c5f2154f8fb3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "id_counter",
        sa.Column("year", sa.Integer, primary_key=True),
        sa.Column("next_seq", sa.Integer, nullable=False),
        sa.CheckConstraint("next_seq >= 1", name="id_counter_next_seq_ge_1"),
    )


def downgrade() -> None:
    op.drop_table("id_counter")
