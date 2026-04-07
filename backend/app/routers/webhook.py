"""
POST /webhook  — receives incoming WhatsApp messages via maytapi.
Writes tasks to Google Sheets instead of a database.
"""
import json
import logging
import os
import tempfile
from datetime import datetime

import httpx
from fastapi import APIRouter, Request

from app.config import settings
from app.services import openai_service, drive_service
from app.services import sheets_service

logger = logging.getLogger("webhook")
router = APIRouter()


def _extract_event(payload: dict) -> dict:
    """Normalise both wrapped {body:{}} and flat payloads."""
    if "body" in payload and isinstance(payload["body"], dict):
        return payload["body"]
    return payload


async def _send_reply(reply_url: str, to_phone: str, text: str):
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(
                reply_url,
                headers={
                    "x-maytapi-key": settings.wa_token,
                    "Content-Type": "application/json",
                },
                json={"to_number": to_phone, "type": "text", "message": text},
            )
    except Exception as exc:
        logger.warning("Failed to send reply: %s", exc)


async def _process_text(raw_text: str, sender: str, sender_name: str) -> str:
    fields = await openai_service.extract_task_fields(raw_text)
    task_id = sheets_service.get_next_task_id()

    sheets_service.append_task({
        "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        "task_id": task_id,
        "task_description": fields.get("task_description", ""),
        "assigned_by": sender_name,
        "assignee_contact": sender,
        "assigned_to": fields.get("assigned_to", ""),
        "employee_email_id": fields.get("employee_email_id", ""),
        "target_date": fields.get("target_date", ""),
        "priority": fields.get("priority", "Medium"),
        "approval_needed": "Yes" if fields.get("approval_needed") else "No",
        "client_name": fields.get("client_name", ""),
        "department": fields.get("department", ""),
        "assigned_name": fields.get("assigned_name") or sender_name,
        "assigned_email_id": fields.get("assigned_email_id", ""),
        "comments": fields.get("comments", ""),
        "source_link": "",
        "status": "Pending",
        "message_type": "text",
    })
    return task_id


async def _process_voice(media_url: str, sender: str, sender_name: str) -> str:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(media_url, headers={"x-maytapi-key": settings.wa_token})
        resp.raise_for_status()
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".ogg")
        tmp.write(resp.content)
        tmp.flush()
        tmp.close()

    try:
        transcription = await openai_service.transcribe_audio(tmp.name)

        drive_url = ""
        if settings.google_drive_folder_id:
            filename = f"voice_{sender}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.ogg"
            drive_url = drive_service.upload_audio_to_drive(tmp.name, filename)

        fields = await openai_service.extract_task_fields(transcription)
        task_id = sheets_service.get_next_task_id()

        sheets_service.append_task({
            "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            "task_id": task_id,
            "task_description": fields.get("task_description", ""),
            "assigned_by": sender_name,
            "assignee_contact": sender,
            "assigned_to": fields.get("assigned_to", ""),
            "employee_email_id": fields.get("employee_email_id", ""),
            "target_date": fields.get("target_date", ""),
            "priority": fields.get("priority", "Medium"),
            "approval_needed": "Yes" if fields.get("approval_needed") else "No",
            "client_name": fields.get("client_name", ""),
            "department": fields.get("department", ""),
            "assigned_name": fields.get("assigned_name") or sender_name,
            "assigned_email_id": fields.get("assigned_email_id", ""),
            "comments": fields.get("comments", ""),
            "source_link": drive_url,
            "status": "Pending",
            "message_type": "voice",
        })
        return task_id
    finally:
        os.unlink(tmp.name)


@router.get("/webhook")
async def webhook_verify(request: Request):
    logger.info("Webhook verification GET received")
    return {"status": "ok"}


@router.post("/webhook")
async def webhook(request: Request):
    payload = await request.json()
    logger.info("WEBHOOK RECEIVED: %s", json.dumps(payload, indent=2))

    event = _extract_event(payload)

    if event.get("type") != "message":
        return {"status": "ignored"}

    msg = event.get("message", {})
    user = event.get("user", {})
    reply_url = event.get("reply", "")

    msg_type = msg.get("type", "")
    msg_id = msg.get("id", "")
    sender = user.get("phone", "") or user.get("id", "")
    sender_name = user.get("name") or event.get("conversation_name") or sender
    from_me = msg.get("fromMe", False)

    logger.info("msg_type=%s sender=%s fromMe=%s", msg_type, sender, from_me)

    if from_me:
        return {"status": "ignored"}

    task_id = None
    error = None

    try:
        if msg_type == "text":
            body: str = msg.get("text", "")
            logger.info("Text body: %r", body)
            if body.lower().startswith("/assign-task"):
                task_id = await _process_text(body, sender, sender_name)

        elif msg_type in ("audio", "ptt", "voice"):
            media_url = msg.get("url")
            if media_url:
                task_id = await _process_voice(media_url, sender, sender_name)

    except Exception as exc:
        logger.exception("Error processing message: %s", exc)
        error = str(exc)

    # Log to Message Logs sheet
    sheets_service.log_message(
        sender=sender,
        msg_type=msg_type,
        raw_text=msg.get("text") or msg.get("url") or "",
        task_id=task_id or "",
        error=error or "",
    )

    if task_id and reply_url:
        await _send_reply(reply_url, sender, f"Task recorded! ID: {task_id}")

    return {"status": "ok"}
