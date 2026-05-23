from sqlalchemy import Engine, text

LEGACY_WORKSPACE_PUBLIC_ID = "legacy-public-workspace"


def ensure_sqlite_workspace_schema(engine: Engine) -> None:
    with engine.begin() as connection:
        _add_column_if_missing(connection, "documents", "workspace_id", "INTEGER")
        _add_column_if_missing(connection, "post_chunks", "workspace_id", "INTEGER")
        _add_column_if_missing(connection, "rag_runs", "workspace_id", "INTEGER")
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_documents_workspace_id ON documents (workspace_id)"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_post_chunks_workspace_id ON post_chunks (workspace_id)"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_rag_runs_workspace_id ON rag_runs (workspace_id)"))
        connection.execute(
            text("INSERT OR IGNORE INTO workspaces (public_id) VALUES (:public_id)"),
            {"public_id": LEGACY_WORKSPACE_PUBLIC_ID},
        )
        legacy_workspace_id = connection.execute(
            text("SELECT id FROM workspaces WHERE public_id = :public_id"),
            {"public_id": LEGACY_WORKSPACE_PUBLIC_ID},
        ).scalar()
        if legacy_workspace_id is not None:
            connection.execute(
                text("UPDATE documents SET workspace_id = :workspace_id WHERE workspace_id IS NULL"),
                {"workspace_id": legacy_workspace_id},
            )
            connection.execute(
                text("UPDATE post_chunks SET workspace_id = :workspace_id WHERE workspace_id IS NULL"),
                {"workspace_id": legacy_workspace_id},
            )
            connection.execute(
                text("UPDATE rag_runs SET workspace_id = :workspace_id WHERE workspace_id IS NULL"),
                {"workspace_id": legacy_workspace_id},
            )


def _add_column_if_missing(connection, table_name: str, column_name: str, column_type: str) -> None:
    columns = {
        row._mapping["name"]
        for row in connection.execute(text(f"PRAGMA table_info({table_name})"))
    }
    if column_name not in columns:
        connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"))
