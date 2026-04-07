"""
POST /webhook  — receives incoming WhatsApp messages via maytapi.

Actual payload format (one message per webhook call):
{
  "type": "message",
  "message": { "type": "text", "text": "...", "id": "..." },
  "user": { "id": "...", "name": "...", "phone": "..." },
  "conversation": "...",
  "conversation_name": "...",
  "reply": "https://api.maytapi.com/api/{product_id}/{phone_id}/sendMessage",
  "timestamp": 1234567890
}

Some events wrap everything inside a "body" key — handled below.
"""
import json
import logging
import os
from datetime import datetime

import httpx
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models.task import MessageLog, Task
from app.services import openai_service, drive_service
from app.utils.task_id import generate_task_id
from app.config import settings

logger = logging.getLogger("webhook")
router = APIRouter()


def _extract_event(payload: dict) -> dict:
    """Normalise both wrapped {body: {...}} and flat payloads."""
    if "body" in payload and isinstance(payload["body"], dict):
        return payload["body"]
    return payload


async def _send_reply(reply_url: str, to_phone: str, text: str):
    """Send a text message back via maytapi reply URL."""
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


async def _process_text(raw_text: str, sender: str, sender_name: str, db: Session):
    fields = await openai_service.extract_task_fields(raw_text)
    task_id = generate_task_id(db)

    task = Task(
        task_id=task_id,
        task_description=fields.get("task_description"),
        assigned_by=sender_name,
        assignee_contact=sender,
        assigned_to=fields.get("assigned_to"),
        employee_email_id=fields.get("employee_email_id"),
        target_date=fields.get("target_date"),
        priority=fields.get("priority", "Medium"),
        approval_needed=1 if fields.get("approval_needed") else 0,
        client_name=fields.get("client_name"),
        department=fields.get("department"),
        assigned_name=fields.get("assigned_name") or sender_name,
        assigned_email_id=fields.get("assigned_email_id"),
        comments=fields.get("comments"),
        source_link=None,
        message_type="text",
        raw_message=raw_text,
    )
    db.add(task)
    db.commit()
    return task_id


async def _process_voice(media_url: str, sender: str, sender_name: str, db: Session):
    import tempfile
    # Download audio from URL
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(media_url, headers={"x-maytapi-key": settings.wa_token})
        resp.raise_for_status()
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".ogg")
        tmp.write(resp.content)
        tmp.flush()
        tmp.close()
        local_path = tmp.name

    try:
        transcription = await openai_service.transcribe_audio(local_path)

        drive_url = None
        if settings.google_drive_folder_id:
            filename = f"voice_{sender}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.ogg"
            drive_url = drive_service.upload_audio_to_drive(local_path, filename)

        fields = await openai_service.extract_task_fields(transcription)
        task_id = generate_task_id(db)

        task = Task(
            task_id=task_id,
            task_description=fields.get("task_description"),
            assigned_by=sender_name,
            assignee_contact=sender,
            assigned_to=fields.get("assigned_to"),
            employee_email_id=fields.get("employee_email_id"),
            target_date=fields.get("target_date"),
            priority=fields.get("priority", "Medium"),
            approval_needed=1 if fields.get("approval_needed") else 0,
            client_name=fields.get("client_name"),
            department=fields.get("department"),
            assigned_name=fields.get("assigned_name") or sender_name,
            assigned_email_id=fields.get("assigned_email_id"),
            comments=fields.get("comments"),
            source_link=drive_url,
            message_type="voice",
            raw_message=transcription,
        )
        db.add(task)
        db.commit()
        return task_id
    finally:
        os.unlink(local_path)


@router.get("/webhook")
async def webhook_verify(request: Request):
    """maytapi GET verification."""
    logger.info("Webhook verification GET received")
    return {"status": "ok"}


@router.post("/webhook")
async def webhook(request: Request, db: Session = Depends(get_db)):
    payload = await request.json()
    logger.info("WEBHOOK RECEIVED: %s", json.dumps(payload, indent=2))

    event = _extract_event(payload)

    # Only process incoming messages (not sent by us)
    if event.get("type") != "message":
        logger.info("Ignoring event type: %s", event.get("type"))
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

    # Skip messages sent by the bot itself
    if from_me:
        return {"status": "ignored"}

    # Log raw message
    log = MessageLog(
        wa_message_id=msg_id,
        sender_number=sender,
        message_type="text" if msg_type == "text" else ("voice" if msg_type in ("audio", "ptt", "voice") else "other"),
        raw_payload=json.dumps(payload),
    )
    db.add(log)
    db.commit()

    task_id = None
    error = None

    try:
        if msg_type == "text":
            body: str = msg.get("text", "")
            logger.info("Text body: %r", body)
            if body.lower().startswith("/assign-task"):
                task_id = await _process_text(body, sender, sender_name, db)

        elif msg_type in ("audio", "ptt", "voice"):
            media_url = msg.get("url")
            if media_url:
                task_id = await _process_voice(media_url, sender, sender_name, db)

    except Exception as exc:
        logger.exception("Error processing message: %s", exc)
        error = str(exc)

    # Update log
    log.processed = 1 if task_id else 0
    log.task_id = task_id
    log.error_message = error
    db.commit()

    if task_id and reply_url:
        await _send_reply(reply_url, sender, f"Task recorded! ID: {task_id}")

    return {"status": "ok"}
