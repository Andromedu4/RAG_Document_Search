"""workspace isolation

Revision ID: 0002_workspace_isolation
Revises: 0001_initial
Create Date: 2026-05-23 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002_workspace_isolation"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LEGACY_WORKSPACE_PUBLIC_ID = "legacy-public-workspace"


def upgrade() -> None:
    op.create_table(
        "workspaces",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("public_id", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_workspaces_public_id", "workspaces", ["public_id"], unique=True)

    op.add_column("documents", sa.Column("workspace_id", sa.Integer(), nullable=True))
    op.add_column("post_chunks", sa.Column("workspace_id", sa.Integer(), nullable=True))
    op.add_column("rag_runs", sa.Column("workspace_id", sa.Integer(), nullable=True))

    op.create_index("ix_documents_workspace_id", "documents", ["workspace_id"])
    op.create_index("ix_post_chunks_workspace_id", "post_chunks", ["workspace_id"])
    op.create_index("ix_rag_runs_workspace_id", "rag_runs", ["workspace_id"])

    op.create_foreign_key(
        "fk_documents_workspace_id_workspaces",
        "documents",
        "workspaces",
        ["workspace_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_post_chunks_workspace_id_workspaces",
        "post_chunks",
        "workspaces",
        ["workspace_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_rag_runs_workspace_id_workspaces",
        "rag_runs",
        "workspaces",
        ["workspace_id"],
        ["id"],
        ondelete="CASCADE",
    )

    workspace_table = sa.table(
        "workspaces",
        sa.column("public_id", sa.String),
    )
    op.bulk_insert(workspace_table, [{"public_id": LEGACY_WORKSPACE_PUBLIC_ID}])

    legacy_workspace_id = (
        f"(SELECT id FROM workspaces WHERE public_id = '{LEGACY_WORKSPACE_PUBLIC_ID}')"
    )
    op.execute(f"UPDATE documents SET workspace_id = {legacy_workspace_id}")
    op.execute(f"UPDATE post_chunks SET workspace_id = {legacy_workspace_id}")
    op.execute(f"UPDATE rag_runs SET workspace_id = {legacy_workspace_id}")


def downgrade() -> None:
    op.drop_constraint("fk_rag_runs_workspace_id_workspaces", "rag_runs", type_="foreignkey")
    op.drop_constraint("fk_post_chunks_workspace_id_workspaces", "post_chunks", type_="foreignkey")
    op.drop_constraint("fk_documents_workspace_id_workspaces", "documents", type_="foreignkey")

    op.drop_index("ix_rag_runs_workspace_id", table_name="rag_runs")
    op.drop_index("ix_post_chunks_workspace_id", table_name="post_chunks")
    op.drop_index("ix_documents_workspace_id", table_name="documents")

    op.drop_column("rag_runs", "workspace_id")
    op.drop_column("post_chunks", "workspace_id")
    op.drop_column("documents", "workspace_id")

    op.drop_index("ix_workspaces_public_id", table_name="workspaces")
    op.drop_table("workspaces")
