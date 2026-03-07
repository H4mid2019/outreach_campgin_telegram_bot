# Telegram AI Personalized Political Email Sender

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
cp .env.example .env
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