"""pytest fixture that seeds corpus_chunks with deterministic test rows."""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone

import pytest_asyncio

SEED_BODIES: list[tuple[str, str, str, str, str]] = [
    # (source_type, source_id, section_path, citation, body)
    (
        "ldc",
        "ldc.6.4.a.2",
        "Chapter 6 / §6.4 / (a)(2)",
        "Manatee County LDC §6.4(a)(2) (2024)",
        "No structure shall be erected without a permit issued under §6.4.",
    ),
    (
        "ldc",
        "ldc.6.5.a",
        "Chapter 6 / §6.5 / (a)",
        "Manatee County LDC §6.5(a) (2024)",
        "Variance applications must be filed at least thirty days before the hearing.",
    ),
    (
        "ldc",
        "ldc.6.6.b",
        "Chapter 6 / §6.6 / (b)",
        "Manatee County LDC §6.6(b) (2024)",
        "Setback requirements for residential zoning shall be twenty feet from street.",
    ),
    (
        "ldc",
        "ldc.7.1.a",
        "Chapter 7 / §7.1 / (a)",
        "Manatee County LDC §7.1(a) (2024)",
        "Conditional use permits require a public hearing before the planning commission.",
    ),
    (
        "ldc",
        "ldc.8.2.c",
        "Chapter 8 / §8.2 / (c)",
        "Manatee County LDC §8.2(c) (2024)",
        "Subdivision plats must include drainage easements and street alignments.",
    ),
    (
        "ordinance",
        "ord.2.4.a",
        "Chapter 2 / §2.4 / (a)",
        "Manatee County Code of Ordinances §2.4(a) (2024)",
        "Procurement of professional services follows the qualifications based selection process.",
    ),
    (
        "ordinance",
        "ord.5.1.b",
        "Chapter 5 / §5.1 / (b)",
        "Manatee County Code of Ordinances §5.1(b) (2024)",
        "Code enforcement liens attach to the property upon recording in the official records.",
    ),
    (
        "ordinance",
        "ord.10.3.a",
        "Chapter 10 / §10.3 / (a)",
        "Manatee County Code of Ordinances §10.3(a) (2024)",
        "Public records requests must be acknowledged within reasonable time per Chapter 119.",
    ),
    (
        "ordinance",
        "ord.15.2.a",
        "Chapter 15 / §15.2 / (a)",
        "Manatee County Code of Ordinances §15.2(a) (2024)",
        "Animal control violations are subject to administrative fines and confiscation.",
    ),
    (
        "ordinance",
        "ord.20.1.a",
        "Chapter 20 / §20.1 / (a)",
        "Manatee County Code of Ordinances §20.1(a) (2024)",
        "Noise ordinances prohibit construction work between 9 PM and 7 AM in residential zones.",
    ),
    (
        "fl_ag_opinion",
        "fl-ag.2023-08",
        "Opinion 2023-08",
        "Fla. AGO 2023-08 (2023)",
        "Florida Attorney General opinion on dual office holding for elected commissioners.",
    ),
    (
        "fl_ag_opinion",
        "fl-ag.2022-15",
        "Opinion 2022-15",
        "Fla. AGO 2022-15 (2022)",
        "Public records exemptions for active code enforcement investigations under Chapter 119.",
    ),
    (
        "fl_ag_opinion",
        "fl-ag.2021-04",
        "Opinion 2021-04",
        "Fla. AGO 2021-04 (2021)",
        "Application of the Sunshine Law to advisory boards lacking final decision-making authority.",
    ),
    (
        "fl_ag_opinion",
        "fl-ag.2020-11",
        "Opinion 2020-11",
        "Fla. AGO 2020-11 (2020)",
        "Florida Attorney General opinion on procurement bid protests and standing.",
    ),
    (
        "fl_ag_opinion",
        "fl-ag.2019-02",
        "Opinion 2019-02",
        "Fla. AGO 2019-02 (2019)",
        "Ethics commission jurisdiction over local government employees under §112.313.",
    ),
    (
        "internal_opinion",
        "internal_opinion.stub.1",
        "opinion / recommendation",
        "Internal Opinion 2026-001",
        "Vested rights claim under pre-amendment LDC §6.4 approval before 2024 amendments.",
    ),
    (
        "internal_opinion",
        "internal_opinion.stub.2",
        "opinion / recommendation",
        "Internal Opinion 2026-002",
        "Notice of violation NOV-2026-117 dated 2026-01-15 requires special magistrate hearing.",
    ),
    (
        "internal_opinion",
        "internal_opinion.stub.3",
        "opinion / recommendation",
        "Internal Opinion 2026-003",
        "RFP procurement protest under Ch. 2-26 procedures and qualifications based selection.",
    ),
    (
        "internal_opinion",
        "internal_opinion.stub.4",
        "opinion / recommendation",
        "Internal Opinion 2026-004",
        "Sunshine Law compliance for citizen advisory boards reviewing comprehensive plan amendments.",
    ),
    (
        "internal_opinion",
        "internal_opinion.stub.5",
        "opinion / recommendation",
        "Internal Opinion 2026-005",
        "Public records exemption claims for ongoing litigation under §119.071(1)(d).",
    ),
    (
        "procedure",
        "procedure.26-104.001.1",
        "Procedure 26-104.001 / §1",
        "Manatee County Procedure 26-104.001 §1 (2024)",
        "RLS form submissions must include matter classification, factual background, and legal question.",
    ),
    (
        "procedure",
        "procedure.26-104.001.2",
        "Procedure 26-104.001 / §2",
        "Manatee County Procedure 26-104.001 §2 (2024)",
        "NOV references must include the NOV date and current administrative status.",
    ),
    (
        "procedure",
        "procedure.26-104.001.3",
        "Procedure 26-104.001 / §3",
        "Manatee County Procedure 26-104.001 §3 (2024)",
        "Critical urgency RLS requires deadline within 15 working days and adverse consequence statement.",
    ),
    (
        "procedure",
        "procedure.26-104.001.4",
        "Procedure 26-104.001 / §4",
        "Manatee County Procedure 26-104.001 §4 (2024)",
        "Procurement RLS must reference applicable Ch. 2-26 provisions and contract dispute history.",
    ),
    (
        "procedure",
        "procedure.26-104.001.5",
        "Procedure 26-104.001 / §5",
        "Manatee County Procedure 26-104.001 §5 (2024)",
        "Public records RLS must specify Chapter 119 exemption claims and redaction history.",
    ),
    (
        "calendar",
        "calendar.holidays.2026",
        "Holidays 2026",
        "Manatee County Working Days Calendar (2026)",
        "New Year's Day January 1, Memorial Day May 25, Independence Day July 4.",
    ),
    (
        "calendar",
        "calendar.holidays.2025",
        "Holidays 2025",
        "Manatee County Working Days Calendar (2025)",
        "New Year's Day January 1, Memorial Day May 26, Independence Day July 4.",
    ),
    (
        "calendar",
        "calendar.holidays.2024",
        "Holidays 2024",
        "Manatee County Working Days Calendar (2024)",
        "New Year's Day January 1, Memorial Day May 27, Independence Day July 4.",
    ),
    (
        "calendar",
        "calendar.holidays.2023",
        "Holidays 2023",
        "Manatee County Working Days Calendar (2023)",
        "New Year's Day January 2, Memorial Day May 29, Independence Day July 4.",
    ),
    (
        "calendar",
        "calendar.holidays.2022",
        "Holidays 2022",
        "Manatee County Working Days Calendar (2022)",
        "New Year's Day January 1, Memorial Day May 30, Independence Day July 4.",
    ),
]


def _deterministic_embedding(seed: str) -> list[float]:
    """Return a 1024-dim unit-norm vector derived from SHA-256 of seed."""
    h = hashlib.sha256(seed.encode()).digest()
    raw = list(h) * (1024 // 32 + 1)
    raw = raw[:1024]
    floats = [(b - 128) / 128.0 for b in raw]
    norm = sum(f * f for f in floats) ** 0.5
    return [f / norm for f in floats]


@pytest_asyncio.fixture()
async def seeded_corpus(db_pool):
    """Seed corpus_chunks with 30 deterministic rows + 1 historical row."""
    base_valid_from = datetime(2024, 1, 1, tzinfo=timezone.utc)
    async with db_pool.acquire() as conn:
        await conn.execute("TRUNCATE corpus_chunks RESTART IDENTITY CASCADE;")
        for source_type, sid, section, citation, body in SEED_BODIES:
            emb = _deterministic_embedding(sid)
            sha = hashlib.sha256(body.encode()).hexdigest()
            await conn.execute(
                """
                INSERT INTO corpus_chunks
                  (source_id, source_type, section_path, citation, body, sha256,
                   valid_from, valid_to, embedding, metadata)
                VALUES ($1, $2, $3, $4, $5, $6, $7, NULL, $8::vector, $9::jsonb)
                """,
                sid,
                source_type,
                section,
                citation,
                body,
                sha,
                base_valid_from,
                str(emb),
                "{}",
            )
        # Historical row: LDC §6.4(a)(2) old version, valid 2022-2024
        old_body = (
            "No structure shall be erected without a permit issued under §6.4 (pre-2024 wording)."
        )
        old_emb = _deterministic_embedding("ldc.6.4.a.2.historical")
        old_sha = hashlib.sha256(old_body.encode()).hexdigest()
        await conn.execute(
            """
            INSERT INTO corpus_chunks
              (source_id, source_type, section_path, citation, body, sha256,
               valid_from, valid_to, embedding, metadata)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9::vector, $10::jsonb)
            """,
            "ldc.6.4.a.2",
            "ldc",
            "Chapter 6 / §6.4 / (a)(2)",
            "Manatee County LDC §6.4(a)(2) (2022)",
            old_body,
            old_sha,
            datetime(2022, 1, 1, tzinfo=timezone.utc),
            datetime(2024, 1, 1, tzinfo=timezone.utc),
            str(old_emb),
            "{}",
        )
    yield db_pool
    async with db_pool.acquire() as conn:
        await conn.execute("TRUNCATE corpus_chunks RESTART IDENTITY CASCADE;")
