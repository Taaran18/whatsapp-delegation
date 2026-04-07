"""
POST /webhook  — receives all incoming WhatsApp messages.

Flow:
  text message starting with /task  →  extract fields via OpenAI  →  save to DB
  voice message                     →  download → Whisper → extract → Drive upload → save to DB
  anything else                     →  logged but ignored
"""
import json
import logging
import os
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from sqlalchemy.orm import Session

logger = logging.getLogger("webhook")

from app.models.database import get_db
from app.models.task import MessageLog, Task
from app.services import openai_service, whatsapp_service, drive_service
from app.utils.task_id import generate_task_id

router = APIRouter()


async def _process_text(raw_text: str, sender: str, sender_name: str, db: Session):
    """Extract task from /task command text and persist."""
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


async def _process_voice(media_id: str, sender: str, sender_name: str, db: Session):
    """Download audio, transcribe, extract, upload to Drive, persist."""
    # 1. Download from WhatsApp
    local_path = await whatsapp_service.download_voice_message(media_id)

    try:
        # 2. Transcribe
        transcription = await openai_service.transcribe_audio(local_path)

        # 3. Upload to Drive
        filename = f"voice_{sender}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.ogg"
        drive_url = drive_service.upload_audio_to_drive(local_path, filename)

        # 4. Extract fields
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


@router.post("/webhook")
async def webhook(request: Request, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    payload = await request.json()
    logger.info("WEBHOOK RECEIVED: %s", json.dumps(payload, indent=2))

    # Log every incoming message
    messages = payload.get("messages", [])
    logger.info("Message count: %d", len(messages))
    for msg in messages:
        msg_id = msg.get("id", "")
        sender = msg.get("from", "")
        sender_name = msg.get("pushName") or msg.get("notifyName") or sender
        msg_type = msg.get("type", "other")

        log = MessageLog(
            wa_message_id=msg_id,
            sender_number=sender,
            message_type=msg_type if msg_type in ("text", "voice") else "other",
            raw_payload=json.dumps(payload),
        )
        db.add(log)
        db.commit()

        task_id = None
        error = None

        try:
            if msg_type == "text":
                body: str = msg.get("text", {}).get("body", "")
                logger.info("Text message from %s: %r", sender, body)
                if body.lower().startswith("/assign-task"):
                    task_id = await _process_text(body, sender, sender_name, db)

            elif msg_type in ("audio", "voice", "ptt"):
                media_id = msg.get("audio", {}).get("id") or msg.get("voice", {}).get("id")
                if media_id:
                    task_id = await _process_voice(media_id, sender, sender_name, db)

        except Exception as exc:
            error = str(exc)

        # Update log with result
        log.processed = 1 if task_id else 0
        log.task_id = task_id
        log.error_message = error
        db.commit()

        if task_id:
            await whatsapp_service.send_text_message(
                sender,
                f"Task recorded! ID: {task_id}",
            )

    return {"status": "ok"}
