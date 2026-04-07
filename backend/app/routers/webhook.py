"""
POST /webhook  — receives incoming WhatsApp messages via maytapi.

Commands handled:
  /task <text>          → extract fields, save to Tasks sheet, confirm
  /update <TASK-ID> ... → fill pending fields on existing task
  voice message         → transcribe, extract, save, confirm
"""
import json
import logging
import os
import re
import tempfile
from datetime import datetime

import httpx
from fastapi import APIRouter, Request

from app.config import settings
from app.services import openai_service, drive_service, sheets_service

logger = logging.getLogger("webhook")
router = APIRouter()


def _extract_event(payload: dict) -> dict:
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


async def _process_text(raw_text: str, sender: str, sender_name: str) -> dict:
    config = sheets_service.get_config_lookup()
    fields = await openai_service.extract_task_fields(raw_text)

    assigned_to    = sheets_service.lookup_employee_full_name(fields.get("assigned_to", ""), config)
    employee_email = fields.get("employee_email_id") or sheets_service.lookup_employee_email(assigned_to, config)
    assigned_name  = sheets_service.lookup_employee_full_name(fields.get("assigned_name") or sender_name, config)
    assigned_email = fields.get("assigned_email_id") or sheets_service.lookup_employee_email(sender_name, config)
    client_name    = sheets_service.lookup_customer_name(fields.get("client_name", ""), config)

    task_id = sheets_service.get_next_task_id()
    task_data = {
        "timestamp":          datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        "task_id":            task_id,
        "task_description":   fields.get("task_description", ""),
        "assigned_by":        sender_name,
        "assignee_contact":   sender,
        "assigned_to":        assigned_to,
        "employee_email_id":  employee_email,
        "target_date":        fields.get("target_date", ""),
        "priority":           fields.get("priority", "Medium"),
        "approval_needed":    "Yes" if fields.get("approval_needed") else "No",
        "client_name":        client_name,
        "department":         fields.get("department", ""),
        "assigned_name":      assigned_name,
        "assigned_email_id":  assigned_email,
        "comments":           fields.get("comments", ""),
        "source_link":        "",
        "status":             "Pending",
        "message_type":       raw_text,
    }
    sheets_service.append_task(task_data)
    return task_data


async def _process_voice(media_url: str, sender: str, sender_name: str) -> dict:
    # Detect file extension from URL
    ext = ".ogg"
    for candidate in [".ogg", ".mp3", ".mp4", ".m4a", ".wav", ".opus"]:
        if candidate in media_url.lower():
            ext = candidate
            break

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.get(media_url, headers={"x-maytapi-key": settings.wa_token})
        resp.raise_for_status()
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
        tmp.write(resp.content)
        tmp.flush()
        tmp.close()

    try:
        # Transcribe (original language) + translate (to English)
        original_text, english_text = await openai_service.transcribe_audio(tmp.name)
        logger.info("Voice transcription: %r | translation: %r", original_text, english_text)

        # Upload to Google Drive
        filename = f"voice_{sender}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}{ext}"
        drive_url = drive_service.upload_audio_to_drive(tmp.name, filename)
        logger.info("Uploaded to Drive: %s", drive_url)

        # Extract task fields from the English translation
        config = sheets_service.get_config_lookup()
        fields = await openai_service.extract_task_fields(english_text)

        assigned_to    = sheets_service.lookup_employee_full_name(fields.get("assigned_to", ""), config)
        employee_email = fields.get("employee_email_id") or sheets_service.lookup_employee_email(assigned_to, config)
        assigned_name  = sheets_service.lookup_employee_full_name(fields.get("assigned_name") or sender_name, config)
        assigned_email = fields.get("assigned_email_id") or sheets_service.lookup_employee_email(sender_name, config)
        client_name    = sheets_service.lookup_customer_name(fields.get("client_name", ""), config)

        task_id = sheets_service.get_next_task_id()
        task_data = {
            "timestamp":          datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            "task_id":            task_id,
            "task_description":   fields.get("task_description", ""),
            "assigned_by":        sender_name,
            "assignee_contact":   sender,
            "assigned_to":        assigned_to,
            "employee_email_id":  employee_email,
            "target_date":        fields.get("target_date", ""),
            "priority":           fields.get("priority", "Medium"),
            "approval_needed":    "Yes" if fields.get("approval_needed") else "No",
            "client_name":        client_name,
            "department":         fields.get("department", ""),
            "assigned_name":      assigned_name,
            "assigned_email_id":  assigned_email,
            "comments":           fields.get("comments", ""),
            "source_link":        drive_url,
            "status":             "Pending",
            # Store original + translation in message_type column
            "message_type":       f"[Voice] {original_text}" if original_text == english_text else f"[Voice] {original_text} | [EN] {english_text}",
        }
        sheets_service.append_task(task_data)
        return task_data
    finally:
        os.unlink(tmp.name)


async def _process_done(raw_text: str, sender: str, reply_url: str):
    """Handle /done TASK-XXXX command."""
    match = re.search(r"(TASK-\d+)", raw_text, re.IGNORECASE)
    if not match:
        await _send_reply(reply_url, sender, "❌ Could not find a Task ID. Use format:\n/done TASK-0001")
        return

    task_id = match.group(1).upper()
    result = sheets_service.mark_task_done(task_id)

    if result is None:
        await _send_reply(reply_url, sender, f"❌ Task {task_id} not found.")
        return

    await _send_reply(reply_url, sender, f"✅ *{task_id}* marked as *Done!*\nUpdated at: {result.get('updated_timestamp', '')}")


async def _process_update(raw_text: str, sender: str, reply_url: str):
    """Handle /update TASK-XXXX ... command."""
    # Extract task ID from message e.g. "/update TASK-0003 email: ..."
    match = re.search(r"(TASK-\d+)", raw_text, re.IGNORECASE)
    if not match:
        await _send_reply(reply_url, sender, "❌ Could not find a Task ID. Use format:\n/update TASK-0001 department: Marketing, email: john@acme.com")
        return

    task_id = match.group(1).upper()
    update_text = raw_text[match.end():].strip()  # everything after the task ID

    if not update_text:
        await _send_reply(reply_url, sender, f"❌ No update info provided. Example:\n/update {task_id} department: Marketing, email: john@acme.com")
        return

    # Use OpenAI to extract what fields to update
    updates = await openai_service.extract_update_fields(update_text)

    if not updates:
        await _send_reply(reply_url, sender, f"❌ Could not understand the update. Example:\n/update {task_id} department: Marketing, email: john@acme.com")
        return

    result = sheets_service.update_task(task_id, updates)

    if result is None:
        await _send_reply(reply_url, sender, f"❌ Task {task_id} not found.")
        return

    # Send updated confirmation
    confirmation = sheets_service.build_confirmation_message(result)
    updated_fields = ", ".join(updates.keys())
    await _send_reply(reply_url, sender, f"✅ *{task_id}* updated!\nFields updated: {updated_fields}\n\n{confirmation}")


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
    sender = user.get("phone", "") or user.get("id", "")
    sender_name = user.get("name") or event.get("conversation_name") or sender
    from_me = msg.get("fromMe", False)

    logger.info("msg_type=%s sender=%s fromMe=%s", msg_type, sender, from_me)

    if from_me:
        return {"status": "ignored"}

    task_data = None
    error = None

    try:
        if msg_type == "text":
            body: str = msg.get("text", "")
            logger.info("Text body: %r", body)

            if body.lower().startswith("/task"):
                task_data = await _process_text(body, sender, sender_name)

            elif body.lower().startswith("/done"):
                await _process_done(body, sender, reply_url)
                sheets_service.log_message(sender, msg_type, body, "", "")
                return {"status": "ok"}

            elif body.lower().startswith("/update"):
                await _process_update(body, sender, reply_url)
                sheets_service.log_message(sender, msg_type, body, "", "")
                return {"status": "ok"}

        elif msg_type in ("audio", "ptt", "voice"):
            media_url = msg.get("url")
            if media_url:
                task_data = await _process_voice(media_url, sender, sender_name)

    except Exception as exc:
        logger.exception("Error processing message: %s", exc)
        error = str(exc)
        if reply_url:
            await _send_reply(reply_url, sender, f"❌ Error processing your message: {exc}")

    sheets_service.log_message(
        sender=sender,
        msg_type=msg_type,
        raw_text=msg.get("text") or msg.get("url") or "",
        task_id=task_data.get("task_id", "") if task_data else "",
        error=error or "",
    )

    # Send confirmation with filled/pending breakdown
    if task_data and reply_url:
        confirmation = sheets_service.build_confirmation_message(task_data)
        await _send_reply(reply_url, sender, confirmation)

    return {"status": "ok"}
