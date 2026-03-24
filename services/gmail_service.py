import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from utils.crypto import CryptoManager
from typing import Tuple, List
from email.mime.base import MIMEBase
import asyncio
import logging
import encodings.idna

logger = logging.getLogger(__name__)


def _encode_email_address(email: str) -> str:
    """Encode email address with IDNA-encoded domain for SMTP delivery.

    Handles internationalized domain names (IDN) like brüssel.diplo.de
    by converting the domain part to its ASCII-compatible encoding (ACE).
    e.g. info@brüssel.diplo.de -> info@xn--brssel-kva.diplo.de
    """
    if "@" not in email:
        return email
    local, domain = email.rsplit("@", 1)
    try:
        # Encode each label of the domain using IDNA
        encoded_labels = [
            encodings.idna.ToASCII(label).decode("ascii") if label else label
            for label in domain.split(".")
        ]
        ascii_domain = ".".join(encoded_labels)
        return f"{local}@{ascii_domain}"
    except (UnicodeError, UnicodeDecodeError):
        # If IDNA encoding fails, return original and let SMTP raise the error
        return email


class GmailService:
    def __init__(self):
        self.crypto = CryptoManager()


    async def send_email(
        self,
        chat_id: int,
        tokens_encrypted: str,
        gmail_email: str,
        to_email: str,
        subject: str,
        body: str,
        mime_payloads: List[MIMEBase] = None,
        max_retries: int = 3,
    ) -> Tuple[bool, str]:
        """Send email via SMTP with app password, retry on errors"""
        app_password = self.crypto.decrypt(tokens_encrypted)
        if not app_password or len(app_password) != 16:
            logger.error(f"Invalid app password for chat_id {chat_id}")
            return False, "خطا در رمز عبور اپلیکیشن Gmail"

        # IDNA-encode recipient domain for SMTP envelope (handles non-ASCII domains)
        smtp_to_email = _encode_email_address(to_email)

        for attempt in range(max_retries):
            try:
                msg = MIMEMultipart()
                msg["From"] = gmail_email
                msg["To"] = to_email  # keep original Unicode form in header
                msg["Subject"] = subject
                msg.attach(MIMEText(body, "plain", "utf-8"))

                if mime_payloads:
                    for payload in mime_payloads:
                        msg.attach(payload)

                server = await asyncio.to_thread(
                    smtplib.SMTP, "smtp.gmail.com", 587, timeout=30
                )
                await asyncio.to_thread(server.starttls)
                await asyncio.to_thread(server.login, gmail_email, app_password)
                text = msg.as_bytes()
                # Use ASCII-compatible address for the SMTP envelope
                await asyncio.to_thread(server.sendmail, gmail_email, smtp_to_email, text)
                await asyncio.to_thread(server.quit)

                logger.info(f"Email sent successfully to {to_email} from chat_id {chat_id}")
                return True, "ارسال موفق"

            except smtplib.SMTPAuthenticationError:
                logger.error(f"SMTP auth failed for chat_id {chat_id}")
                return False, "رمز عبور اشتباه است. App Password جدید بسازید."
            except smtplib.SMTPServerDisconnected:
                logger.warning(
                    f"SMTP disconnected for chat_id {chat_id}, retry {attempt + 1}"
                )
            except Exception as e:
                error_msg = str(e)
                logger.error(f"Send failed for {to_email}: {error_msg}")
                if "rate limit" in error_msg.lower() or "too many" in error_msg.lower():
                    wait_time = (2**attempt) + 5
                    logger.warning(f"Rate limit detected, wait {wait_time}s")
                    await asyncio.sleep(wait_time)
                else:
                    return False, f"خطا: {error_msg}"

        return False, "تلاش‌های ارسال ناموفق (محدودیت نرخ یا قطع اتصال)"
