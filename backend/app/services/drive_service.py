"""
Upload voice message files to Google Drive and return a shareable link.
Uses a service account for authentication (no user OAuth flow needed).
"""
import os
from pathlib import Path

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from app.config import settings

SCOPES = ["https://www.googleapis.com/auth/drive.file"]


def _get_drive_service():
    creds = service_account.Credentials.from_service_account_file(
        settings.google_service_account_json, scopes=SCOPES
    )
    return build("drive", "v3", credentials=creds)


def upload_audio_to_drive(local_path: str, filename: str) -> str:
    """
    Upload a file to the configured Google Drive folder.
    Returns a publicly readable shareable URL.
    """
    service = _get_drive_service()

    file_metadata = {
        "name": filename,
        "parents": [settings.google_drive_folder_id],
    }
    media = MediaFileUpload(local_path, mimetype="audio/ogg", resumable=False)

    uploaded = (
        service.files()
        .create(body=file_metadata, media_body=media, fields="id")
        .execute()
    )
    file_id = uploaded["id"]

    # Make the file readable by anyone with the link
    service.permissions().create(
        fileId=file_id,
        body={"role": "reader", "type": "anyone"},
    ).execute()

    return f"https://drive.google.com/file/d/{file_id}/view"
