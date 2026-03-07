import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from utils.crypto import CryptoManager
from typing import Tuple
import asyncio
import logging

logger = logging.getLogger(__name__)

class GmailService:
    def __init__(self):
        self.crypto = CryptoManager()

    async def send_email(self, chat_id: int, tokens_encrypted: str, gmail_email: str, 
                        to_email: str, subject: str, body: str, max_retries: int = 3) -> Tuple[bool, str]:
        """Send email via SMTP with app password, retry on errors"""
        app_password = self.crypto.decrypt(tokens_encrypted)
        if not app_password or len(app_password) != 16:
            logger.error(f"Invalid app password for chat_id {chat_id}")
            return False, "خطا در رمز عبور اپلیکیشن Gmail"

        for attempt in range(max_retries):
            try:
                msg = MIMEMultipart()
                msg['From'] = gmail_email
                msg['To'] = to_email
                msg['Subject'] = subject
                msg.attach(MIMEText(body, 'plain', 'utf-8'))

                server = await asyncio.to_thread(
                    smtplib.SMTP, 'smtp.gmail.com', 587, timeout=30
                )
                await asyncio.to_thread(server.starttls)
                await asyncio.to_thread(server.login, gmail_email, app_password)
                text = msg.as_string()
                await asyncio.to_thread(server.sendmail, gmail_email, to_email, text)
                await asyncio.to_thread(server.quit)
                
                logger.info(f"Email sent successfully to {to_email} from chat_id {chat_id}")
                return True, "ارسال موفق"
                
            except smtplib.SMTPAuthenticationError:
                logger.error(f"SMTP auth failed for chat_id {chat_id}")
                return False, "رمز عبور اشتباه است. App Password جدید بسازید."
            except smtplib.SMTPServerDisconnected:
                logger.warning(f"SMTP disconnected for chat_id {chat_id}, retry {attempt+1}")
            except Exception as e:
                error_msg = str(e)
                logger.error(f"Send failed for {to_email}: {error_msg}")
                if 'rate limit' in error_msg.lower() or 'too many' in error_msg.lower():
                    wait_time = (2 ** attempt) + 5
                    logger.warning(f"Rate limit detected, wait {wait_time}s")
                    await asyncio.sleep(wait_time)
                else:
                    return False, f"خطا: {error_msg}"
        
        return False, "تلاش‌های ارسال ناموفق (محدودیت نرخ یا قطع اتصال)"
