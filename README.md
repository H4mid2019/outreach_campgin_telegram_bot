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
- ✅ **Preset Campaigns** — shared, DB-stored campaigns with pre-loaded email lists and targets

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

## Preset Campaigns

Preset campaigns are shared across all users and stored in the database. Each campaign bundles a **target/context** and a **full email list** so users can launch a campaign in one click without manually uploading a CSV or typing a context.

### User Flow
1. Click **📝 Draft** or **📤 Autosend**
2. Bot shows a list of all preset campaigns as buttons, plus **✏️ ورود دستی** (manual entry)
3. Select a preset → email list + target are pre-loaded automatically
4. Enter only the **sender name** → emails are generated/sent

### Creating & Updating Campaigns (Admin)
Requires the `CAMPAIGN_ACCESS_KEY` from `.env`.

**Via button:**
- Main menu → **📋 مدیریت کمپین‌ها** → enter key → **➕ افزودن / به‌روزرسانی کمپین**

**Via command:**
- Send `/addcampaign` → enter key → admin panel

**Steps to add/update a campaign:**
1. **Name** — unique slug (e.g. `eu-meps-2024`). If the name already exists, it will be **updated**.
2. **Description** — short label shown in the campaign picker (e.g. "EU MEPs climate letter").
3. **Target** — campaign context/goal used as the AI prompt (e.g. "Request support for Climate Action Bill X. Formal tone.").
4. **Email list** — upload a `.csv` file **or** paste CSV text in format:
   ```
   name,email,info,language
   John Doe,john@eu.com,MEP,en
   Jane Smith,jane@bg.com,Bulgaria,bg
   ```

### Deleting Campaigns (Admin)
Main menu → **📋 مدیریت کمپین‌ها** → enter key → **🗑 حذف کمپین** → select → confirm.

### Listing Campaigns (Public)
Send `/campaigns` to list all preset campaigns without authentication.

### Environment Variables
| Variable | Default | Description |
|---|---|---|
| `CAMPAIGN_ACCESS_KEY` | `CampaignAdmin2024` | Secret key required to create/update/delete campaigns |

---

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
- ✅ **کمپین‌های پیش‌تنظیم** — کمپین‌های مشترک ذخیره‌شده در DB با لیست ایمیل و هدف از پیش تعریف‌شده

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

## کمپین‌های پیش‌تنظیم

کمپین‌های پیش‌تنظیم بین همه کاربران مشترک هستند و در دیتابیس ذخیره می‌شوند. هر کمپین شامل یک **هدف/زمینه** و یک **لیست ایمیل کامل** است تا کاربران بتوانند بدون آپلود CSV یا تایپ زمینه، کمپین را با یک کلیک راه‌اندازی کنند.

### جریان کاربری
1. روی **📝 Draft** یا **📤 Autosend** کلیک کنید
2. ربات لیست کمپین‌های پیش‌تنظیم را به صورت دکمه نمایش می‌دهد + گزینه **✏️ ورود دستی**
3. یک کمپین انتخاب کنید → لیست ایمیل + هدف به صورت خودکار بارگذاری می‌شوند
4. فقط **نام فرستنده** را وارد کنید → ایمیل‌ها تولید/ارسال می‌شوند

### ایجاد و به‌روزرسانی کمپین (مدیر)
نیاز به `CAMPAIGN_ACCESS_KEY` از فایل `.env` دارد.

**از طریق دکمه:**
- منوی اصلی ← **📋 مدیریت کمپین‌ها** ← کلید را وارد کنید ← **➕ افزودن / به‌روزرسانی کمپین**

**از طریق دستور:**
- ارسال `/addcampaign` ← کلید را وارد کنید ← پنل مدیریت

**مراحل افزودن/به‌روزرسانی کمپین:**
1. **نام** — slug یکتا (مثال: `eu-meps-2024`). اگر نام از قبل وجود داشته باشد، **به‌روزرسانی** می‌شود.
2. **توضیح** — برچسب کوتاه در لیست انتخاب کمپین (مثال: "نامه آب‌وهوا به MEPهای اروپا").
3. **هدف** — زمینه/هدف کمپین که به عنوان پرامپت AI استفاده می‌شود.
4. **لیست ایمیل** — آپلود فایل `.csv` یا paste متن CSV:
   ```
   name,email,info,language
   John Doe,john@eu.com,MEP,en
   Jane Smith,jane@bg.com,Bulgaria,bg
   ```

### حذف کمپین (مدیر)
منوی اصلی ← **📋 مدیریت کمپین‌ها** ← کلید ← **🗑 حذف کمپین** ← انتخاب ← تأیید.

### مشاهده لیست کمپین‌ها (عمومی)
دستور `/campaigns` را بدون نیاز به احراز هویت ارسال کنید.

### متغیرهای محیطی
| متغیر | پیش‌فرض | توضیح |
|---|---|---|
| `CAMPAIGN_ACCESS_KEY` | `CampaignAdmin2024` | کلید مخفی برای ایجاد/به‌روزرسانی/حذف کمپین‌ها |

---

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
