# Telegram AI Personalized Political Email Sender

**Professional Telegram bot for generating and sending personalized formal emails to politicians (Bulgarian MPs) with AI.**

## Features
- ✅ Full Persian UI
- ✅ Copyable draft (CSV + template)
- ✅ Automatic sending from Gmail (OAuth2)
- ✅ AI personalization (OpenRouter/Claude-3.5-Sonnet)
- ✅ Ultra formal tone en/bg
- ✅ CSV validation, delay, retry
- ✅ SQLite database, encrypted tokens

## Installation
1. **Clone/Copy the project**
   ```
   cd email_political_ai_bot
   ```

2. **Install dependencies**
   ```
   pip install -r requirements.txt
   ```

3. **Set up .env** (copy from .env.example)
   ```
   copy .env.example .env
   ```
   - `BOT_TOKEN`: from @BotFather
   - `OPENROUTER_API_KEY`: [openrouter.ai](https://openrouter.ai)
   - `ENCRYPTION_KEY`: `openssl rand -base64 32`
   - `GMAIL_CLIENT_ID` / `GMAIL_CLIENT_SECRET`: [Google Cloud Console](https://console.cloud.google.com) → OAuth2 → Authorized redirect: `http://127.0.0.1:8000/callback`

4. **Run**
   ```
   python main.py
   ```
   - FastAPI: http://127.0.0.1:8000
   - Bot: polling starts

## Usage
1. `/start` → Draft or Autosend
2. **Draft**: CSV → template (e.g. `Subject: Hello {name}\nBody: ... {company}`)
3. **Autosend**: `/status` → Connect Gmail → CSV → Persian context → Send

## Local Testing
- ngrok for remote callback: `ngrok http 8000` → update redirect_uri
- Sample CSV:
  ```
  name,email,company,language
  John Doe,john@example.com,MP GERB,en
  ```

## Security
- Fernet encrypted tokens
- CSV max 300, valid emails
- Gmail scopes only `gmail.send`

## Logs
- `bot.log`
- DB: `email_bot.db`

## Troubleshooting
- Gmail callback: check localhost/port, Google Console
- AI: valid API key
- CSV: UTF-8 encoding

---

# ربات تلگرام AI فرستنده ایمیل سیاسی شخصی‌سازی‌شده

ربات تلگرام حرفه‌ای برای تولید و ارسال ایمیل‌های رسمی شخصی‌سازی‌شده به سیاستمداران (MPs بلغارستان) با AI.

## ویژگی‌ها
- ✅ UI کامل فارسی
- ✅ پیش‌نویس قابل کپی (CSV + قالب)
- ✅ ارسال خودکار از Gmail (OAuth2)
- ✅ AI شخصی‌سازی (OpenRouter/Claude-3.5-Sonnet)
- ✅ لحن فوق رسمی en/bg
- ✅ اعتبارسنجی CSV، تأخیر، retry
- ✅ دیتابیس SQLite، tokens رمزنگاری‌شده

## نصب
1. **کلون/کپی پروژه**
   ```
   cd email_political_ai_bot
   ```

2. **نصب وابستگی‌ها**
   ```
   pip install -r requirements.txt
   ```

3. **تنظیم .env** (از .env.example کپی کنید)
   ```
   copy .env.example .env
   ```
   - `BOT_TOKEN`: از @BotFather
   - `OPENROUTER_API_KEY`: [openrouter.ai](https://openrouter.ai)
   - `ENCRYPTION_KEY`: `openssl rand -base64 32`
   - `GMAIL_CLIENT_ID` / `GMAIL_CLIENT_SECRET`: [Google Cloud Console](https://console.cloud.google.com) → OAuth2 → Authorized redirect: `http://127.0.0.1:8000/callback`

4. **اجرا**
   ```
   python main.py
   ```
   - FastAPI: http://127.0.0.1:8000
   - Bot: polling شروع می‌شود

## استفاده
1. `/start` → Draft یا Autosend
2. **Draft**: CSV → قالب (e.g. `Subject: سلام {name}\nBody: ... {company}`)
3. **Autosend**: `/status` → Connect Gmail → CSV → زمینه فارسی → ارسال

## تست محلی
- ngrok برای callback remote: `ngrok http 8000` → redirect_uri بروزرسانی
- CSV نمونه:
  ```
  name,email,company,language
  John Doe,john@example.com,MP GERB,en
  ```

## امنیت
- Tokens Fernet رمزنگاری
- CSV max 300، valid emails
- Gmail scopes فقط `gmail.send`

## لاگ‌ها
- `bot.log`
- DB: `email_bot.db`

## مشکلات؟
- Gmail callback: localhost/port چک، Google Console
- AI: API key معتبر
- CSV: UTF-8 encoding
