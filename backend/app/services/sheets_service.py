"""
Google Sheets service.

Tabs:
  Tasks        — A:R  (main task data)
  Message Logs — A:F  (raw log)
  Config       — A: Name, B: Mail ID, D: Customer Name
"""
import json
from datetime import datetime

from google.oauth2 import service_account
from googleapiclient.discovery import build

from app.config import settings

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

TASK_COLUMNS = [
    "timestamp", "task_id", "task_description", "assigned_by",
    "assignee_contact", "assigned_to", "employee_email_id", "target_date",
    "priority", "approval_needed", "client_name", "department",
    "assigned_name", "assigned_email_id", "comments", "source_link",
    "status", "message_type",
]

TASK_DISPLAY_NAMES = {
    "task_description":  "Task Description",
    "assigned_to":       "Assigned To",
    "employee_email_id": "Employee Email",
    "target_date":       "Target Date",
    "priority":          "Priority",
    "approval_needed":   "Approval Needed",
    "client_name":       "Client Name",
    "department":        "Department",
    "assigned_name":     "Assigned Name",
    "assigned_email_id": "Assigned Email",
    "comments":          "Comments",
}


def _get_service():
    if settings.google_service_account_json_content:
        info = json.loads(settings.google_service_account_json_content)
        creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    else:
        creds = service_account.Credentials.from_service_account_file(
            settings.google_service_account_json, scopes=SCOPES
        )
    return build("sheets", "v4", credentials=creds)


# ── Config sheet lookup ───────────────────────────────────────────────────────

def get_config_lookup() -> dict:
    """
    Returns:
      {
        "employees": { "Taaran Jain": "jain.taaran@e-marketing.io", ... },
        "customers":  ["Acme Corp", "Bikaner Polymers", ...]
      }
    """
    service = _get_service()
    result = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=settings.google_sheet_id, range="Config!A2:D")
        .execute()
    )
    rows = result.get("values", [])
    employees = {}
    customers = []
    for row in rows:
        # pad to 4 cols
        row += [""] * (4 - len(row))
        name, email, _, customer = row[0], row[1], row[2], row[3]
        if name and email:
            employees[name.strip().lower()] = email.strip()
        if customer:
            customers.append(customer.strip())
    return {"employees": employees, "customers": customers}


def lookup_employee_email(name: str, config: dict) -> str:
    """Return email if name matches an employee in Config, else empty string."""
    if not name:
        return ""
    return config["employees"].get(name.strip().lower(), "")


# ── Task ID ───────────────────────────────────────────────────────────────────

def get_next_task_id() -> str:
    service = _get_service()
    result = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=settings.google_sheet_id, range="Tasks!B:B")
        .execute()
    )
    count = len(result.get("values", []))
    return f"TASK-{count:04d}"


# ── Tasks ─────────────────────────────────────────────────────────────────────

def append_task(task_data: dict) -> None:
    service = _get_service()
    row = [str(task_data.get(col, "") or "") for col in TASK_COLUMNS]
    (
        service.spreadsheets()
        .values()
        .append(
            spreadsheetId=settings.google_sheet_id,
            range="Tasks!A:R",
            valueInputOption="USER_ENTERED",
            body={"values": [row]},
        )
        .execute()
    )


def get_all_tasks(status: str = None, priority: str = None, limit: int = 100, offset: int = 0) -> list[dict]:
    service = _get_service()
    result = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=settings.google_sheet_id, range="Tasks!A2:R")
        .execute()
    )
    rows = result.get("values", [])
    tasks = []
    for row in rows:
        row += [""] * (len(TASK_COLUMNS) - len(row))
        task = dict(zip(TASK_COLUMNS, row))
        if status and task.get("status") != status:
            continue
        if priority and task.get("priority") != priority:
            continue
        tasks.append(task)
    tasks.reverse()
    return tasks[offset: offset + limit]


def get_task_by_id(task_id: str) -> dict | None:
    tasks = get_all_tasks()
    for t in tasks:
        if t.get("task_id") == task_id:
            return t
    return None


def update_task(task_id: str, updates: dict) -> dict | None:
    service = _get_service()
    result = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=settings.google_sheet_id, range="Tasks!B:B")
        .execute()
    )
    rows = result.get("values", [])
    row_index = None
    for i, row in enumerate(rows):
        if row and row[0] == task_id:
            row_index = i + 1
            break
    if row_index is None:
        return None

    for col_name, value in updates.items():
        if col_name in TASK_COLUMNS:
            col_letter = chr(ord("A") + TASK_COLUMNS.index(col_name))
            (
                service.spreadsheets()
                .values()
                .update(
                    spreadsheetId=settings.google_sheet_id,
                    range=f"Tasks!{col_letter}{row_index}",
                    valueInputOption="USER_ENTERED",
                    body={"values": [[str(value)]]},
                )
                .execute()
            )

    return get_task_by_id(task_id)


# ── Confirmation message builder ──────────────────────────────────────────────

def build_confirmation_message(task: dict) -> str:
    """Build the WhatsApp reply showing filled and pending fields."""
    filled = []
    pending = []

    for col, label in TASK_DISPLAY_NAMES.items():
        val = task.get(col, "")
        if val and val.strip():
            filled.append(f"  • {label}: {val}")
        else:
            pending.append(f"  • {label}")

    lines = [f"✅ Task Recorded! ID: *{task['task_id']}*", ""]

    if filled:
        lines.append("📋 *Details Recorded:*")
        lines.extend(filled)

    if pending:
        lines.append("")
        lines.append("⏳ *Pending Details:*")
        lines.extend(pending)
        lines.append("")
        lines.append(f"To fill pending details, reply:\n*/update {task['task_id']}*\nfollowed by the missing info in natural language.")
        lines.append(f"\nExample:\n/update {task['task_id']} department: Marketing, email: john@acme.com, approval: yes")

    return "\n".join(lines)


# ── Message Logs ──────────────────────────────────────────────────────────────

def log_message(sender: str, msg_type: str, raw_text: str, task_id: str = "", error: str = "") -> None:
    service = _get_service()
    row = [
        datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        sender,
        msg_type,
        raw_text[:500],
        task_id,
        error,
    ]
    (
        service.spreadsheets()
        .values()
        .append(
            spreadsheetId=settings.google_sheet_id,
            range="Message Logs!A:F",
            valueInputOption="USER_ENTERED",
            body={"values": [row]},
        )
        .execute()
    )
