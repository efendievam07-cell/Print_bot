"""initial schema

Revision ID: a1b2c3d4e5f6
Revises:
Create Date: 2026-06-10 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(length=255), nullable=True),
        sa.Column("is_admin", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("telegram_id"),
    )

    op.create_table(
        "print_jobs",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("order_numbers", sa.Text(), nullable=False),
        sa.Column("image_path", sa.String(length=512), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "PENDING",
                "PRINTING",
                "SUCCESS",
                "ERROR",
                name="print_job_status",
                native_enum=False,
            ),
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("printed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "assets",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "asset_type",
            sa.Enum(
                "LOGO",
                "QR_IOS",
                "QR_ANDROID",
                name="asset_type",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("file_path", sa.String(length=512), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("asset_type"),
    )


def downgrade() -> None:
    op.drop_table("assets")
    op.drop_table("print_jobs")
    op.drop_table("users")
