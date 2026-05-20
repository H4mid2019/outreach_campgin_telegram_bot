# Campaign Creation Runbook

Standard workflow for spinning up a new preset campaign in the outreach bot.
The user pastes raw material; the assistant produces every bot-ready artifact
in one round-trip.

---

## 1. What the user pastes (minimum required)

```
RECIPIENTS:
<one email per line, OR a comma-separated blob>

SUBJECTS:
<one or more candidate subject lines — used only to infer the theme>

BODIES:
<one or more sample email bodies — used only to distill the target directive>

OPTIONAL:
- language:        en           # ISO-2; default en
- sender name:     The People of Iran
- attachments:     none
- year tag in slug: no
```

That's it. Subjects and bodies are *seed material*, never pasted into the bot.

---

## 2. What the assistant produces

1. **Slug** (the campaign `name` field) — lowercase, dashed, ≤50 chars
2. **Description** — short Persian label shown on the picker button
3. **Target** — the AI directive injected as `Campaign context/goal:` into every email prompt
4. **CSV** — saved as `output_<slug>.csv` at project root, matching the bot's schema
5. **Telegram admin steps** — the exact button sequence the user runs on their phone

---

## 3. Hard constraints (from the code — never violate)

| Field | Rule | Source |
|-------|------|--------|
| `name` | regex `^[a-z0-9\-_]{1,50}$` | [handlers/campaigns.py:314](handlers/campaigns.py#L314) |
| `description` | ≥3 chars | [handlers/campaigns.py:354](handlers/campaigns.py#L354) |
| `target` | ≥10 chars | [handlers/campaigns.py:383](handlers/campaigns.py#L383) |
| CSV header | exactly `name,email,info,language` | [utils/csv_validator.py:21](utils/csv_validator.py#L21) |
| CSV row limit | ≤300 | [utils/csv_validator.py:26](utils/csv_validator.py#L26) |
| Email regex | `^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$` | [utils/csv_validator.py:38](utils/csv_validator.py#L38) |
| `language` | 2-letter ISO; falls back to `en` | [utils/csv_validator.py:52](utils/csv_validator.py#L52) |
| Default model | `google/gemini-2.5-flash-lite` | [config.py:14-16](config.py#L14-L16) |

---

## 4. System-prompt rules that shape the target directive

Pulled from [config.py:50-103](config.py#L50-L103). The model is told to:

- Produce **150–200 words, 3 paragraphs**, subject **5–9 words**, diplomatic register
- Refuse a set of activist-tone phrases. **Strip these from any target you write**, or the model will mirror them back:
  - `urge`, `I urge`, `champion`, `demand`, `insist`, `push for`, `fight for`
  - `I am writing to`, `I hope this message finds you well`
  - `it is imperative/crucial/vital that`
  - `I strongly/firmly/deeply believe`
- Default salutation when no gender profile: `Dear [Full Name],`

The seed bodies a user pastes will almost always contain banned words.
Distill the *strategy*, never the *prose*.

---

## 5. Step-by-step procedure

### Step 1 — Slug

- Topic-first: `fifa-lion-and-sun-flag`, `eu-meps-climate`, `un-iran-protests`
- Add `-YYYY` only if the campaign is time-bound
- ≤50 chars; verify against the regex above
- Re-using an existing slug **updates** the campaign in place

### Step 2 — Description (Persian)

- One line, scannable on a phone button
- Pattern: `<target org> — <action>`
  - Example: `اعتراض به فیفا — لغو ممنوعیت پرچم شیر و خورشید`
- Em-dash (`—`) is fine here; it lives in the DB as UTF-8

### Step 3 — Target directive

Read the seed bodies, then write English prose that captures:

1. **The specific ask** (1 sentence)
2. **The framing / justification** (2–3 sentences)
3. **The contradiction or moral weight** (1–2 sentences)
4. **The voice** ("formal diplomatic, written on behalf of …")
5. **Institutional anchors to cite** (FIFA Human Rights Policy, UN Charter Article X, etc.)

Aim 600–1500 chars. Strip every forbidden phrase before saving.
Do **not** paste seed bodies verbatim.

### Step 4 — CSV

Header row: `name,email,info,language`

For each recipient:

- **Name** — short, human-readable, produces a sensible salutation
  - ✅ `FIFA Legal Team`, `Office of Senator Cruz`
  - ❌ `FIFA Legal Division` (model writes "Dear Mr. Division,")
- **Info** — `<org> - <role/department>`
- **Hyphens in info: ASCII `-` only**, never em-dash `—` (Windows CSV safety)
- **Language** — ISO-2 of the recipient's working language; default `en`

Sort policy-relevant recipients first; drop or push operational helpdesks
to the bottom.

Validate before saving:
- Every email matches the regex
- ≤300 rows
- Any field containing a comma is wrapped in `"..."`

Save as `output_<slug>.csv` at project root.

### Step 5 — Classify recipients honestly

If the user's list contains operational mailboxes that won't act on the
request (ticketing, transfer helpdesks, GDPR/DPO inboxes, payment desks),
flag them and recommend dropping. Don't silently bloat the campaign and
don't burn the user's sender reputation on bounces.

### Step 6 — Hand-off message to the user

Always print, in this order:

1. Final slug
2. Final Persian description
3. Final target inside a copyable code block
4. Suggested sender name
5. The Telegram admin button-sequence:

```
/start → 📋 مدیریت کمپین‌ها → enter CAMPAIGN_ACCESS_KEY
→ ➕ افزودن / به‌روزرسانی کمپین
→ name:        <slug>
→ description: <persian>
→ target:      <paste the block>
→ upload:      output_<slug>.csv
→ /skip (or upload PDF attachments, then /done)
```

---

## 6. Copy-paste template (give this to the user)

```
RECIPIENTS:


SUBJECTS:


BODIES:


OPTIONAL:
- language: en
- sender name:
- attachments: none
- year tag in slug: no
```

---

## 7. Reference: existing campaigns produced with this runbook

| Slug | CSV | Notes |
|------|-----|-------|
| `fifa-lion-and-sun-flag` | [output_fifa_lion_sun.csv](output_fifa_lion_sun.csv) | 5 policy-relevant FIFA inboxes; ops helpdesks dropped |
