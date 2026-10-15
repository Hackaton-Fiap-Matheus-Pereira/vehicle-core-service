"""Cria usuários e catálogo canônico de veículos.

Revision ID: 0001
Revises:
Create Date: 2026-10-15
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("full_name", sa.String(length=120), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=False)

    op.create_table(
        "vehicles",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("brand", sa.String(length=80), nullable=False),
        sa.Column("model", sa.String(length=120), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("color", sa.String(length=50), nullable=False),
        sa.Column("price", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "AVAILABLE",
                "RESERVED",
                "SOLD",
                name="vehicle_status",
                native_enum=False,
                length=16,
            ),
            nullable=False,
            server_default="AVAILABLE",
        ),
        sa.Column(
            "sync_status",
            sa.Enum(
                "PENDING",
                "SYNCED",
                "FAILED",
                name="sync_status",
                native_enum=False,
                length=16,
            ),
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column("source_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_by_user_id", sa.String(length=36), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_vehicles_brand", "vehicles", ["brand"], unique=False)
    op.create_index("ix_vehicles_model", "vehicles", ["model"], unique=False)
    op.create_index("ix_vehicles_price", "vehicles", ["price"], unique=False)
    op.create_index("ix_vehicles_status", "vehicles", ["status"], unique=False)
    op.create_index("ix_vehicles_sync_status", "vehicles", ["sync_status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_vehicles_sync_status", table_name="vehicles")
    op.drop_index("ix_vehicles_status", table_name="vehicles")
    op.drop_index("ix_vehicles_price", table_name="vehicles")
    op.drop_index("ix_vehicles_model", table_name="vehicles")
    op.drop_index("ix_vehicles_brand", table_name="vehicles")
    op.drop_table("vehicles")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
