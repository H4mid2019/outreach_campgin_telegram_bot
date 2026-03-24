import os
import shutil
import mimetypes
from email.mime.base import MIMEBase
from email import encoders
from typing import List, Dict
from config import Config


def sanitize_filename(filename: str) -> str:
    """Sanitize filename for storage, remove invalid chars, limit length."""
    invalid_chars = '<>:"\\|/\\?*'
    for char in invalid_chars:
        filename = filename.replace(char, "_")
    name, ext = os.path.splitext(filename)
    return f"{name[:90]}{ext}"


def get_campaign_dir(campaign_name: str) -> str:
    """Get or create campaign attachment directory."""
    path = os.path.join(Config.CAMPAIGN_ATTACHMENTS_PATH, campaign_name)
    os.makedirs(path, exist_ok=True)
    return path


def save_attachment(
    temp_file_path: str, campaign_name: str, original_filename: str
) -> Dict[str, any]:
    """Save Telegram document to campaign dir, return metadata."""
    filename = sanitize_filename(original_filename)
    dir_path = get_campaign_dir(campaign_name)
    full_path = os.path.join(dir_path, filename)

    # Avoid overwrite by appending number if exists
    counter = 1
    base_filename = filename
    while os.path.exists(full_path):
        name, ext = os.path.splitext(base_filename)
        filename = f"{name}_{counter}{ext}"
        full_path = os.path.join(dir_path, filename)
        counter += 1

    shutil.copy2(temp_file_path, full_path)

    size = os.path.getsize(full_path)
    mime_type, _ = mimetypes.guess_type(full_path)

    return {
        "filename": filename,
        "relative_path": os.path.join(campaign_name, filename),
        "size_bytes": size,
        "mime_type": mime_type or "application/octet-stream",
    }


def load_mime_payloads(attachments: List[Dict]) -> List[MIMEBase]:
    """Load attachments into MIME payloads for email."""
    payloads = []
    for att in attachments:
        full_path = os.path.join(Config.CAMPAIGN_ATTACHMENTS_PATH, att["relative_path"])
        if os.path.exists(full_path):
            with open(full_path, "rb") as f:
                mime_str = att.get("mime_type") or mimetypes.guess_type(full_path)[0] or "application/octet-stream"
                maintype, subtype = mime_str.split("/", 1)
                part = MIMEBase(maintype, subtype)
                part.set_payload(f.read())
            encoders.encode_base64(part)
            part.add_header(
                "Content-Disposition", 'attachment; filename="%s"' % att["filename"]
            )
            payloads.append(part)
    return payloads


def cleanup_campaign_attachments(campaign_name: str) -> bool:
    """Delete campaign attachment directory."""
    dir_path = get_campaign_dir(campaign_name)
    if os.path.exists(dir_path):
        shutil.rmtree(dir_path)
        return True
    return False


def copy_attachments_to_retry(
    source_campaign: str, target_campaign: str, attachments_metadata: List[Dict]
) -> List[Dict]:
    """Copy attachments to retry campaign dir, update metadata."""
    source_dir = get_campaign_dir(source_campaign)
    target_dir = get_campaign_dir(target_campaign)
    copied = []
    for att in attachments_metadata:
        src_path = os.path.join(source_dir, att["filename"])
        if os.path.exists(src_path):
            dst_path = os.path.join(target_dir, att["filename"])
            shutil.copy2(src_path, dst_path)
            copied.append(
                {
                    "filename": att["filename"],
                    "relative_path": os.path.join(target_campaign, att["filename"]),
                    "size_bytes": os.path.getsize(dst_path),
                    "mime_type": att["mime_type"],
                }
            )
    return copied
