"""
Downloads media (voice messages) from the WhatsApp unofficial API.
"""
import httpx
import os
import tempfile

from app.config import settings

HEADERS = {
    "Authorization": f"Bearer {settings.wa_token}",
    "Content-Type": "application/json",
}


async def download_voice_message(media_id: str) -> str:
    """
    Download a voice message by media_id.
    Returns local temp file path (caller is responsible for cleanup).
    """
    url = f"{settings.wa_base_url}/media/{media_id}"
    async with httpx.AsyncClient(timeout=30) as client:
        # Step 1: get the download URL
        resp = await client.get(url, headers=HEADERS)
        resp.raise_for_status()
        data = resp.json()
        download_url = data.get("url") or data.get("link")

        # Step 2: stream the actual file
        async with client.stream("GET", download_url, headers=HEADERS) as stream:
            stream.raise_for_status()
            suffix = ".ogg"
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
            async for chunk in stream.aiter_bytes(chunk_size=8192):
                tmp.write(chunk)
            tmp.flush()
            tmp.close()
            return tmp.name


async def send_text_message(to: str, text: str) -> None:
    """Send a plain text reply to a WhatsApp number."""
    url = f"{settings.wa_base_url}/messages"
    payload = {
        "to": to,
        "type": "text",
        "text": {"body": text},
    }
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(url, json=payload, headers=HEADERS)
        resp.raise_for_status()
