"""baseline RLS Apex v0.2.0a tables.

Revision ID: 001
Revises:
Create Date: 2026-05-08
"""
from alembic import op

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # pgvector for B3+ retrieval phase. DEFERRED to v0.2.1 — extension not
    # installed in local Postgres@16 and pgvector isn't required for v0.2.0a
    # baseline tables. Re-enable when retrieval phase lands.
    # op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("""
        CREATE TABLE rls (
            rls_id text PRIMARY KEY,
            matter_id text,
            classification text NOT NULL CHECK (classification IN ('privileged','public_record','confidential')),
            status text NOT NULL CHECK (status IN ('Draft','NeedsFixes','ReadyForCAO','Acknowledged','NeedsRevision','Rejected')),
            type text NOT NULL CHECK (type IN ('permit_or_zoning','procurement','public_records','code_enforcement_litigation','general_advisory')),
            subject text NOT NULL CHECK (length(subject) <= 240),
            department text NOT NULL,
            contact_name text NOT NULL,
            contact_extension text NOT NULL,
            payload jsonb NOT NULL DEFAULT '{}'::jsonb,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            lineage_head text NOT NULL CHECK (lineage_head ~ '^[0-9a-f]{64}$')
        )
    """)
    op.execute("""
        CREATE TABLE lineage_event (
            id bigserial PRIMARY KEY,
            rls_id text NOT NULL REFERENCES rls(rls_id) DEFERRABLE INITIALLY DEFERRED,
            sequence integer NOT NULL CHECK (sequence >= 1),
            prev_hash text CHECK (prev_hash IS NULL OR prev_hash ~ '^[0-9a-f]{64}$'),
            this_hash text NOT NULL CHECK (this_hash ~ '^[0-9a-f]{64}$'),
            payload jsonb NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            UNIQUE (rls_id, sequence)
        )
    """)
    op.execute("""
        CREATE TABLE audit_event (
            id bigserial PRIMARY KEY,
            rls_id text,
            actor_id text NOT NULL,
            actor_role text NOT NULL,
            action text NOT NULL,
            payload jsonb NOT NULL,
            idempotency_key text,
            created_at timestamptz NOT NULL DEFAULT now(),
            UNIQUE (idempotency_key)
        )
    """)
    op.execute("""
        CREATE TABLE validation_result (
            id bigserial PRIMARY KEY,
            rls_id text NOT NULL,
            blocking jsonb NOT NULL,
            warnings jsonb NOT NULL,
            ran_at timestamptz NOT NULL DEFAULT now()
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS validation_result")
    op.execute("DROP TABLE IF EXISTS audit_event")
    op.execute("DROP TABLE IF EXISTS lineage_event")
    op.execute("DROP TABLE IF EXISTS rls")
