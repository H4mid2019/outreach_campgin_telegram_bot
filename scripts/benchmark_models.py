"""
benchmark_models.py
-------------------
Standalone script to compare LLM models on OpenRouter for political outreach email generation.
Mimics the EXACT same API calls, prompts, and settings used by the Telegram bot.

Usage:
    python scripts/benchmark_models.py

Requirements:
    - OPENROUTER_API_KEY set in .env
    - pip install openai python-dotenv
"""

import asyncio
import time
import os
import sys

# Add project root to path so we can import config
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

import openai

# ─────────────────────────────────────────────
# CONFIG (mirrors config.py exactly)
# ─────────────────────────────────────────────
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Models to benchmark
MODELS = [
    # ("x-ai/grok-4.1-fast",                          "Grok 4.1 Fast          [CURRENT - paid ~$10/40K emails]"),
    # ("meta-llama/llama-4-scout",                     "Llama 4 Scout          [RECOMMENDED - paid ~$6/40K emails]"),
    # ("google/gemini-2.5-flash-lite",                 "Gemini 2.5 Flash Lite  [BUDGET - paid ~$6.80/40K emails]"),
    ("minimax/minimax-m2.5", "Minimax M2.5            [Free tier, not for production]"),
    # ("meta-llama/llama-3.3-70b-instruct",       "Llama 3.3 70B          [BUDGET -paid ~$6.80/40K emails]"),
    # ("openai/gpt-4o",                            "GPT-4o                 [Premium fallback, paid]"),
    # ("meta-llama/llama-4-maverick",             "Llama 4 Maverick       [Higher quality, paid ~$11/40K emails]"),
    # ("anthropic/claude-haiku-4.5",              "Claude Haiku 4.5       [Fast + great quality, paid]"),
    # ("anthropic/claude-sonnet-4.5",             "Claude Sonnet 4.5      [Top quality, paid]"),
]

# ─────────────────────────────────────────────
# SYSTEM PROMPT — imported directly from Config so it stays in sync
# ─────────────────────────────────────────────
from config import Config


def get_system_prompt(lang: str) -> str:
    return Config.get_system_prompt(lang)


# ─────────────────────────────────────────────
# USER PROMPT (mirrors EmailGenerator.generate_personalized_email exactly)
# ─────────────────────────────────────────────
def build_user_prompt() -> str:
    # ── Campaign ──────────────────────────────────
    context = (
        "Support the democratic transition in Iran and advocate for formal recognition of "
        "Crown Prince Reza Pahlavi as the legitimate representative of the Iranian people "
        "during the transition period toward a free and democratic Iran."
    )

    # ── Recipient ─────────────────────────────────
    name = "Ted Cruz"
    info = (
        "U.S. Senator (Texas), Member of Senate Foreign Relations Committee, "
        "Republican Party, known for hawkish Iran policy and pro-sanctions stance"
    )
    lang = "en"
    sender_name = "Alexander Mitchell"

    # ── Profile (simulates Tavily research result) ─
    profile = {
        "bio": (
            "Ted Cruz is a U.S. Senator from Texas and a member of the Senate Foreign Relations "
            "Committee. He is a leading voice on Iran sanctions, regime accountability, and "
            "support for the Iranian people's freedom aspirations. He has consistently called "
            "the Iranian regime a state sponsor of terrorism."
        ),
        "gender": "male",
        "targets": [
            "Iran regime accountability",
            "democratic transition",
            "US national security",
        ],
        "mottos": [
            "Stand with the Iranian people",
            "No nuclear deal with terrorists",
            "Freedom over appeasement",
        ],
        "values": ["rule of law", "freedom", "democracy", "American leadership"],
        "keywords": [
            "Iran sanctions",
            "regime change",
            "human rights",
            "Crown Prince Pahlavi",
            "state sponsor of terrorism",
            "freedom fighters",
        ],
        "subjects": [
            "Iran nuclear deal opposition",
            "Iranian opposition support",
            "sanctions enforcement",
        ],
    }

    # ── Build prompt (exact copy of EmailGenerator logic) ─
    user_prompt = f"""Campaign context/goal: {context}

Recipient details:
- Full name: {name}
- Position/Party/Info: {info}
- Language: {lang}
- Sender name (use EXACTLY in closing): {sender_name}"""

    user_prompt += f"""

Recipient profile from research:
Bio: {profile.get("bio", "")}
Gender: {profile.get("gender", "unknown")}
Targets: {", ".join(profile.get("targets", []))}
Mottos: {", ".join(profile.get("mottos", []))}
Values: {", ".join(profile.get("values", []))}
Keywords: {", ".join(profile.get("keywords", []))}
Subjects: {", ".join(profile.get("subjects", []))}

Use profile for hyper-personalization. Match language/style. Official clickbait subjects using keywords/mottos."""

    user_prompt += """

Generate a personalized email using the exact structure from system prompt. Use the sender name exactly in the closing signature, no placeholders."""

    return user_prompt


# ─────────────────────────────────────────────
# PARSE RESPONSE (mirrors openrouter_service.py)
# ─────────────────────────────────────────────
def parse_response(content: str) -> dict:
    if "Subject:" in content and "Body:" in content:
        subject = content.split("Subject:")[1].split("\n\nBody:")[0].strip()
        body = content.split("Body:")[1].strip()
        return {"subject": subject, "body": body}
    else:
        lines = content.split("\n")
        if lines:
            first_line = lines[0].strip()
            if first_line.startswith("Subject:"):
                subject = first_line.split(":", 1)[1].strip()
                body = "\n".join(lines[1:]).strip()
            else:
                subject = first_line or "Formal Request"
                body = "\n".join(lines[1:]).strip()
            return {"subject": subject, "body": body}
        return {"subject": "Formal Request", "body": ""}


# ─────────────────────────────────────────────
# BENCHMARK A SINGLE MODEL
# ─────────────────────────────────────────────
async def benchmark_model(
    client: openai.AsyncOpenAI, model_id: str, system_prompt: str, user_prompt: str
) -> dict:
    start = time.perf_counter()
    error = None
    result = None

    try:
        response = await client.chat.completions.create(
            model=model_id,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            max_tokens=500,
        )
        elapsed = time.perf_counter() - start
        content = response.choices[0].message.content.strip()
        result = parse_response(content)
        usage = response.usage
        return {
            "elapsed": elapsed,
            "subject": result["subject"],
            "body": result["body"],
            "prompt_tokens": usage.prompt_tokens if usage else "n/a",
            "completion_tokens": usage.completion_tokens if usage else "n/a",
            "total_tokens": usage.total_tokens if usage else "n/a",
            "raw": content,
            "error": None,
        }
    except Exception as e:
        elapsed = time.perf_counter() - start
        return {
            "elapsed": elapsed,
            "subject": "",
            "body": "",
            "prompt_tokens": "n/a",
            "completion_tokens": "n/a",
            "total_tokens": "n/a",
            "raw": "",
            "error": str(e),
        }


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
async def main():
    if not OPENROUTER_API_KEY:
        print("❌  OPENROUTER_API_KEY not set in .env")
        return

    client = openai.AsyncOpenAI(
        api_key=OPENROUTER_API_KEY,
        base_url=OPENROUTER_BASE_URL,
    )

    system_prompt = get_system_prompt("en")
    user_prompt = build_user_prompt()

    print("\n" + "=" * 72)
    print("  OPENROUTER MODEL BENCHMARK — Political Outreach Email")
    print(
        "  Campaign: Support Iranian Revolution / Recognize Crown Prince Reza Pahlavi"
    )
    print("  Recipient: Senator Ted Cruz  |  Language: English")
    print("=" * 72)
    print(f"  Testing {len(MODELS)} models sequentially...\n")

    results = []

    for model_id, label in MODELS:
        print(f"  ⏳  {label.split('[')[0].strip()} ...", end="", flush=True)
        data = await benchmark_model(client, model_id, system_prompt, user_prompt)
        results.append((model_id, label, data))
        status = f"✅  {data['elapsed']:.2f}s" if not data["error"] else "❌  FAILED"
        print(f"\r  {status}  {label}")

    # ── Detailed output ────────────────────────────────────────────────────────
    print("\n\n" + "═" * 72)
    print("  DETAILED RESULTS")
    print("═" * 72)

    for model_id, label, data in results:
        print(f"\n{'─' * 72}")
        print(f"  MODEL : {label}")
        print(f"  ID    : {model_id}")
        print(
            f"  Time  : {data['elapsed']:.2f}s   |   Tokens: {data['prompt_tokens']} in / {data['completion_tokens']} out / {data['total_tokens']} total"
        )
        print(f"{'─' * 72}")
        if data["error"]:
            print(f"  ❌  ERROR: {data['error']}")
        else:
            print(f"  SUBJECT : {data['subject']}\n")
            print("  BODY:\n")
            for line in data["body"].split("\n"):
                print(f"    {line}")

    # ── Summary table ──────────────────────────────────────────────────────────
    print("\n\n" + "═" * 72)
    print("  PERFORMANCE SUMMARY")
    print("─" * 72)
    print(f"  {'Model':<45} {'Time':>7}  {'In':>6}  {'Out':>6}  Status")
    print(f"  {'─' * 45} {'─' * 7}  {'─' * 6}  {'─' * 6}  {'─' * 6}")
    for model_id, label, data in results:
        short_label = label.split("[")[0].strip()
        status = "✅ OK" if not data["error"] else "❌ FAIL"
        t = f"{data['elapsed']:.2f}s"
        print(
            f"  {short_label:<45} {t:>7}  {str(data['prompt_tokens']):>6}  {str(data['completion_tokens']):>6}  {status}"
        )
    print("═" * 72 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
