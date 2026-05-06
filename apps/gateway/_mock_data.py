"""Mock fixtures for DEV_MODE. Mirrors window.SAMPLE in src/data.jsx.

Single source for both surfaces: the React prototype's inline data and the
gateway's `/api/*` endpoints return identical shapes. When SGLang lands the
endpoint implementations swap to real backends; the React tree doesn't change.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

# ─── Submissions (RLS list/detail) ────────────────────────────────

SUBMISSIONS: list[dict[str, Any]] = [
    {
        "id": "RLS-26-0142",
        "title": "Code enforcement: 4810 26th St W — repeat zoning violation",
        "type": "Code Enforcement", "matter": "Litigation",
        "requester": "Code Enforcement Officer", "department": "Code Enforcement",
        "status": "Acknowledged", "urgency": "Standard",
        "submitted": "2026-05-04", "deadline": "2026-05-15",
        "workingDays": 8, "assignee": "Litigation Attorney", "team": "General Litigation",
        "completeness": 94, "risk": "Medium", "bie": False, "attachments": 7,
        "activity": [3, 1, 0, 4, 2, 1, 0, 5, 2, 1, 3, 6, 2, 0, 1],
    },
    {
        "id": "RLS-26-0141",
        "title": "Proposed ordinance — short-term rental amendment §125.66(3)(c)",
        "type": "Ordinance", "matter": "Drafting",
        "requester": "Planning Officer", "department": "Planning & Zoning",
        "status": "Assigned", "urgency": "Critical",
        "submitted": "2026-05-03", "deadline": "2026-05-18",
        "workingDays": 11, "assignee": "Senior Counsel", "team": "Land Use",
        "completeness": 81, "risk": "High", "bie": True, "attachments": 12,
        "activity": [0, 2, 1, 3, 4, 5, 2, 7, 4, 3, 8, 5, 2, 1, 0],
    },
    {
        "id": "RLS-26-0140",
        "title": "Public records request — body-cam retention policy",
        "type": "Public Records", "matter": "Advisory",
        "requester": "Sheriff's Office", "department": "Sheriff",
        "status": "Submitted", "urgency": "Urgent",
        "submitted": "2026-05-03", "deadline": "2026-05-12",
        "workingDays": 5, "assignee": "—", "team": "—",
        "completeness": 100, "risk": "Low", "bie": False, "attachments": 3,
        "activity": [0, 0, 1, 0, 0, 2, 1, 0, 0, 0, 1, 3, 0, 0, 0],
    },
    {
        "id": "RLS-26-0139",
        "title": "Contract review — Kimley-Horn traffic study amendment 04",
        "type": "Contract", "matter": "Review",
        "requester": "Public Works", "department": "Public Works",
        "status": "Complete", "urgency": "Standard",
        "submitted": "2026-04-28", "deadline": "2026-05-08",
        "workingDays": 0, "assignee": "Contracts Attorney", "team": "Contracts",
        "completeness": 100, "risk": "Low", "bie": False, "attachments": 5,
        "activity": [2, 1, 4, 3, 2, 5, 6, 4, 3, 2, 1, 0, 0, 0, 0],
    },
    {
        "id": "RLS-26-0138",
        "title": "Tree canopy preservation — appeal of admin decision",
        "type": "Litigation", "matter": "Advisory",
        "requester": "Parks & Natural Resources", "department": "Parks & Natural Resources",
        "status": "Assigned", "urgency": "Standard",
        "submitted": "2026-04-27", "deadline": "2026-05-11",
        "workingDays": 4, "assignee": "Litigation Attorney", "team": "Land Use",
        "completeness": 88, "risk": "Medium", "bie": False, "attachments": 4,
        "activity": [1, 0, 2, 3, 1, 0, 4, 2, 3, 1, 5, 2, 0, 0, 1],
    },
    {
        "id": "RLS-26-0137",
        "title": "Stormwater utility fee — methodology challenge",
        "type": "Litigation", "matter": "Litigation",
        "requester": "Utilities Dept", "department": "Utilities",
        "status": "Draft", "urgency": "Standard",
        "submitted": "—", "deadline": "2026-05-22",
        "workingDays": 13, "assignee": "—", "team": "—",
        "completeness": 42, "risk": "—", "bie": False, "attachments": 1,
        "activity": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 2, 0, 0],
    },
    {
        "id": "RLS-26-0136",
        "title": "ADA accommodation grievance — Library District",
        "type": "Advisory", "matter": "Advisory",
        "requester": "Library Services", "department": "Library",
        "status": "Acknowledged", "urgency": "Urgent",
        "submitted": "2026-04-26", "deadline": "2026-05-08",
        "workingDays": 1, "assignee": "Senior Counsel", "team": "Employment",
        "completeness": 96, "risk": "Medium", "bie": False, "attachments": 6,
        "activity": [0, 1, 0, 2, 4, 1, 3, 2, 0, 5, 4, 2, 1, 3, 1],
    },
    {
        "id": "RLS-26-0135",
        "title": "Procurement protest — IT managed services RFP-2026-08",
        "type": "Procurement", "matter": "Advisory",
        "requester": "Procurement", "department": "Procurement",
        "status": "Rejected", "urgency": "Standard",
        "submitted": "2026-04-23", "deadline": "—",
        "workingDays": -2, "assignee": "—", "team": "—",
        "completeness": 60, "risk": "—", "bie": False, "attachments": 2,
        "activity": [0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    },
]

# ─── Dashboard KPIs ───────────────────────────────────────────────

KPIS = {
    "active": 47, "thisWeek": 18, "overdue": 3, "awaitingAck": 6,
    "avgTurnDays": 7.4, "slaPct": 94, "completenessAvg": 87, "aiAssisted": 71,
}

# ─── Team load ────────────────────────────────────────────────────

TEAM_LOAD = [
    {"team": "General Litigation", "lead": "Litigation Attorney",   "open": 14, "capacity": 18, "breaching": 1},
    {"team": "Land Use",            "lead": "Senior Counsel",  "open": 11, "capacity": 14, "breaching": 1},
    {"team": "Contracts",           "lead": "Contracts Attorney", "open":  9, "capacity": 16, "breaching": 0},
    {"team": "Employment",          "lead": "Employment Attorney", "open":  7, "capacity": 12, "breaching": 0},
    {"team": "Public Records",      "lead": "Public Records Specialist",  "open":  6, "capacity": 10, "breaching": 1},
]

# ─── Compliance pulse ─────────────────────────────────────────────

COMPLIANCE_PULSE = [
    {"rule": "Individual attachments (no combined PDFs)", "pct":  96, "n": 142},
    {"rule": "Director signature on critical / urgent",   "pct":  88, "n":  31},
    {"rule": "BIE filed for proposed ordinances §125.66(3)(c)", "pct": 73, "n": 11},
    {"rule": "Word format for draft contracts",           "pct":  91, "n":  47},
    {"rule": "50-char subject limit",                     "pct":  99, "n": 142},
    {"rule": "Public-records flag (Public Records Dept only)", "pct": 100, "n": 9},
]

# ─── Activity queue ───────────────────────────────────────────────

QUEUE = [
    {"time": "11:42", "id": "RLS-26-0142", "who": "Code Enforcement Officer",   "action": "Submitted",                                "urgent": False},
    {"time": "11:29", "id": "RLS-26-0141", "who": "RLS Validator",     "action": "Risk re-classified → High",                "urgent": True},
    {"time": "10:58", "id": "RLS-26-0140", "who": "Sheriff's Office", "action": "Submitted with 3 attachments",            "urgent": False},
    {"time": "10:11", "id": "RLS-26-0139", "who": "Contracts Attorney",        "action": "Marked complete",                          "urgent": False},
    {"time": "09:48", "id": "RLS-26-0136", "who": "Senior Counsel",         "action": "Acknowledged · ADA grievance",            "urgent": False},
    {"time": "09:02", "id": "RLS-26-0138", "who": "Litigation Attorney",          "action": "Routing accepted (Land Use)",             "urgent": False},
    {"time": "08:31", "id": "RLS-26-0141", "who": "Planning Officer",           "action": "Added BIE worksheet v3",                   "urgent": False},
    {"time": "08:14", "id": "RLS-26-0142", "who": "RLS Validator",      "action": "Auto-suggested team: General Lit.",        "urgent": False},
]

# ─── Inbox ────────────────────────────────────────────────────────

INBOX = [
    {"id": "RLS-26-0140", "from": "Sheriff's Office",  "subject": "Public records request — body-cam retention",       "preview": "Routine 119 request; recommend Public Records Dept handle.",   "unread": True},
    {"id": "RLS-26-0136", "from": "Library Services",  "subject": "ADA accommodation grievance — Library District",    "preview": "Urgent — patron filed yesterday; needs response by 5/8.",      "unread": True},
    {"id": "RLS-26-0142", "from": "Code Enforcement Officer",      "subject": "4810 26th St W — repeat zoning violation",          "preview": "Third citation in 18 months; ready for litigation review.",    "unread": False},
]

# ─── Drafts ───────────────────────────────────────────────────────

DRAFTS = [
    {"id": "DRAFT-26-0014", "title": "Tower lease — Ridgewood Cell Co. amendment 02",
     "department": "Public Works", "updated": "2026-05-04", "completeness": 64,
     "blockers": ["Missing director signature", "BIE required (§125.66(3)(c))"]},
    {"id": "DRAFT-26-0013", "title": "Vendor MSA — DataPlatform LLC",
     "department": "Procurement", "updated": "2026-05-03", "completeness": 88,
     "blockers": ["Word format required"]},
    {"id": "DRAFT-26-0012", "title": "Settlement memo — Smith v. Manatee County",
     "department": "Legal", "updated": "2026-05-02", "completeness": 100,
     "blockers": []},
]

# ─── 14-day rolling counters ──────────────────────────────────────

INCOMING_14 = [4, 6, 3, 5, 2, 7, 9, 5, 4, 8, 6, 7, 3, 5]
CLOSED_14   = [3, 5, 4, 4, 3, 6, 7, 6, 5, 6, 7, 5, 4, 6]


def all_payload() -> dict[str, Any]:
    """Composite for `/api/sample` — single-shot fixture for the React tree."""
    return {
        "submissions": deepcopy(SUBMISSIONS),
        "dashboardKpis": deepcopy(KPIS),
        "teamLoad": deepcopy(TEAM_LOAD),
        "compliancePulse": deepcopy(COMPLIANCE_PULSE),
        "queue": deepcopy(QUEUE),
        "inbox": deepcopy(INBOX),
        "drafts": deepcopy(DRAFTS),
        "incoming14": list(INCOMING_14),
        "closed14": list(CLOSED_14),
    }
