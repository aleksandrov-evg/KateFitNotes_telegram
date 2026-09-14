"""Место проведения для каждого типа тренировки.

Revision ID: 0003_train_location
Revises: 0002_site_model
Create Date: 2026-09-14
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0003_train_location"
down_revision: Union[str, None] = "0002_site_model"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE main.trains "
        "ADD COLUMN location text NOT NULL DEFAULT 'ter_fit'"
    )
    op.execute(
        "UPDATE main.trains SET location = 'home' "
        "WHERE type_train = '[дом] Реформер'"
    )
    op.execute(
        "ALTER TABLE main.trains "
        "ADD CONSTRAINT trains_location_check "
        "CHECK (location IN ('home', 'ter_fit'))"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE main.trains DROP COLUMN location")
