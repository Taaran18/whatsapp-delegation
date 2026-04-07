"""
Google Sheets service — replaces the database layer.

Sheet: "WhatsApp Delegation"
  Tab 1: Tasks         (columns A–R)
  Tab 2: Message Logs  (columns A–F)
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

LOG_COLUMNS = [
    "received_at", "sender_number", "message_type",
    "raw_text", "task_id_created", "error",
]


def _get_service():
    if settings.google_service_account_json_content:
        info = json.loads(settings.google_service_account_json_content)
        creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    else:
        creds = service_account.Credentials.from_service_account_file(
            settings.google_service_account_json, scopes=SCOPES
        )
    return build("sheets", "v4", credentials=creds)


# ── Task ID generation ────────────────────────────────────────────────────────

def get_next_task_id() -> str:
    """Count existing task rows and return next sequential ID."""
    service = _get_service()
    result = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=settings.google_sheet_id, range="Tasks!B:B")
        .execute()
    )
    rows = result.get("values", [])
    count = len(rows)  # includes header row; count=1 means no tasks yet
    return f"TASK-{count:04d}"


# ── Tasks ─────────────────────────────────────────────────────────────────────

def append_task(task_data: dict) -> None:
    """Append one task row to the Tasks sheet."""
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
    """Read all task rows and return as list of dicts."""
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
        row += [""] * (len(TASK_COLUMNS) - len(row))  # pad short rows
        task = dict(zip(TASK_COLUMNS, row))
        if status and task.get("status") != status:
            continue
        if priority and task.get("priority") != priority:
            continue
        tasks.append(task)

    # newest first (sheet stores oldest first)
    tasks.reverse()
    return tasks[offset: offset + limit]


def update_task(task_id: str, updates: dict) -> dict | None:
    """Find row by task_id and update specified columns."""
    service = _get_service()

    # Find the row index
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
            row_index = i + 1  # sheet rows are 1-indexed
            break

    if row_index is None:
        return None

    # Update each changed column individually
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

    # Return updated task
    result = (
        service.spreadsheets()
        .values()
        .get(
            spreadsheetId=settings.google_sheet_id,
            range=f"Tasks!A{row_index}:R{row_index}",
        )
        .execute()
    )
    row = result.get("values", [[]])[0]
    row += [""] * (len(TASK_COLUMNS) - len(row))
    return dict(zip(TASK_COLUMNS, row))


# ── Message Logs ──────────────────────────────────────────────────────────────

def log_message(sender: str, msg_type: str, raw_text: str, task_id: str = "", error: str = "") -> None:
    """Append a row to the Message Logs tab."""
    service = _get_service()
    row = [
        datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        sender,
        msg_type,
        raw_text[:500],  # truncate long payloads
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
