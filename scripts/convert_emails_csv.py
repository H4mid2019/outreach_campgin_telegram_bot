#!/usr/bin/env python3
"""
convert_emails_csv.py
====================
Standalone script to convert a flat email-list CSV into sample_draft.csv format:
    name,email,info,language

Usage:
    python convert_emails_csv.py <input.csv> [output.csv]

    If output.csv is omitted, it defaults to sample_draft.csv

Requirements (install via pip):
    pip install openai tavily-python ddgs pandas tqdm python-dotenv requests

API keys (set in .env or environment variables):
    OPENROUTER_API_KEY   – Required for AI enrichment
    TAVILY_API_KEY       – Optional; used as a search fallback / extra data source
"""

import os
import re
import sys
import json
import time
import logging
import argparse
from pathlib import Path

import pandas as pd
from tqdm import tqdm
from dotenv import load_dotenv

# ──────────────────────────────────────────────────────────────────────────────
# Load .env from any ancestor directory (for running from project root)
# ──────────────────────────────────────────────────────────────────────────────
for parent in [Path(__file__).parent, Path(__file__).parent.parent]:
    env_path = parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        break
else:
    load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Static knowledge tables
# ──────────────────────────────────────────────────────────────────────────────

# TLD → (country_name, iso_lang, fallback_info)
TLD_META: dict[str, tuple[str, str, str]] = {
    "ca": ("Canada", "en", "Canadian Politics"),
    "fr": ("France", "fr", "French Politics"),
    "au": ("Australia", "en", "Australian Politics"),
    "uk": ("UK", "en", "UK Politics"),
    "se": ("Sweden", "sv", "Swedish Politics"),
    "it": ("Italy", "it", "Italian Politics"),
    "es": ("Spain", "es", "Spanish Politics"),
    "dk": ("Denmark", "da", "Danish Politics"),
    "no": ("Norway", "no", "Norwegian Politics"),
    "at": ("Austria", "de", "Austrian Politics"),
    "nl": ("Netherlands", "nl", "Dutch Politics"),
    "hu": ("Hungary", "hu", "Hungarian Politics"),
    "ch": ("Switzerland", "de", "Swiss Politics"),
    "de": ("Germany", "de", "German Politics"),
    "be": ("Belgium", "nl", "Belgian Politics"),
    "pl": ("Poland", "pl", "Polish Politics"),
    "cz": ("Czech Republic", "cs", "Czech Politics"),
    "sk": ("Slovakia", "sk", "Slovak Politics"),
    "ro": ("Romania", "ro", "Romanian Politics"),
    "bg": ("Bulgaria", "bg", "Bulgarian Politics"),
    "hr": ("Croatia", "hr", "Croatian Politics"),
    "si": ("Slovenia", "sl", "Slovenian Politics"),
    "pt": ("Portugal", "pt", "Portuguese Politics"),
    "gr": ("Greece", "el", "Greek Politics"),
    "fi": ("Finland", "fi", "Finnish Politics"),
    "lt": ("Lithuania", "lt", "Lithuanian Politics"),
    "lv": ("Latvia", "lv", "Latvian Politics"),
    "ee": ("Estonia", "et", "Estonian Politics"),
    "ie": ("Ireland", "en", "Irish Politics"),
    "lu": ("Luxembourg", "fr", "Luxembourg Politics"),
    "mt": ("Malta", "en", "Maltese Politics"),
    "cy": ("Cyprus", "el", "Cypriot Politics"),
    "eu": ("EU", "en", "EU / MEP"),
    "int": ("International", "en", "International Organization"),
    "org": ("International", "en", "NGO / Organization"),
    "com": ("International", "en", "Organization"),
    "net": ("International", "en", "Organization"),
    "gov": ("USA", "en", "US Government"),
}

# Known domain fragments → (category, country, language)
# Checked as `fragment in domain.lower()`
DOMAIN_HINTS: dict[str, tuple[str, str, str]] = {
    # Canada
    "parl.gc.ca": ("Member of Parliament", "Canada", "en"),
    "pm.gc.ca": ("Prime Minister's Office", "Canada", "en"),
    "gc.ca": ("Canadian Government", "Canada", "en"),
    # France
    "assemblee-nationale.fr": ("Member of Parliament", "France", "fr"),
    "senat.fr": ("Senator", "France", "fr"),
    "diplomatie.gouv.fr": ("Ministry of Foreign Affairs", "France", "fr"),
    "interieur.gouv.fr": ("Ministry of Interior", "France", "fr"),
    "pm.gouv.fr": ("Prime Minister's Office", "France", "fr"),
    "gouv.fr": ("French Government", "France", "fr"),
    "parti-renaissance.fr": ("Renaissance Party", "France", "fr"),
    "rassemblementnational.fr": ("Rassemblement National", "France", "fr"),
    "lafranceinsoumise.fr": ("La France Insoumise", "France", "fr"),
    "republicains.fr": ("Les Républicains", "France", "fr"),
    "partisocialiste.fr": ("Parti Socialiste", "France", "fr"),
    "eelv.fr": ("Europe Écologie Les Verts", "France", "fr"),
    "cncdh.fr": ("Human Rights Commission", "France", "fr"),
    "defenseurdesdroits.fr": ("Defender of Rights", "France", "fr"),
    "pcf.fr": ("PCF", "France", "fr"),
    # Australia
    "aph.gov.au": ("Member of Parliament", "Australia", "en"),
    "gov.au": ("Australian Government", "Australia", "en"),
    # UK
    "parliament.uk": ("Member of Parliament", "UK", "en"),
    "fcdo.gov.uk": ("Foreign Affairs", "UK", "en"),
    "labour.org.uk": ("Labour Party", "UK", "en"),
    "conservativeparty.org.uk": ("Conservative Party", "UK", "en"),
    "libdems.org.uk": ("Liberal Democrats", "UK", "en"),
    "snp.org": ("SNP", "UK", "en"),
    "greenparty.org.uk": ("Green Party", "UK", "en"),
    "amnesty.org.uk": ("Amnesty International", "UK", "en"),
    "theguardian.com": ("Media", "UK", "en"),
    "thetimes.co.uk": ("Media", "UK", "en"),
    "bbc.co.uk": ("Media", "UK", "en"),
    "equalityhumanrights.com": ("Equality & Human Rights", "UK", "en"),
    # Sweden
    "riksdagen.se": ("Member of Parliament", "Sweden", "sv"),
    "regeringskansliet.se": ("Government Office", "Sweden", "sv"),
    # Italy
    "esteri.it": ("Ministry of Foreign Affairs", "Italy", "it"),
    "camera.it": ("Member of Parliament", "Italy", "it"),
    "legaonline.it": ("Lega Party", "Italy", "it"),
    "partitodemocratico.it": ("Partito Democratico", "Italy", "it"),
    "forzaitalia.it": ("Forza Italia", "Italy", "it"),
    "movimento5stelle.it": ("Movimento 5 Stelle", "Italy", "it"),
    "fratelli-italia.it": ("Fratelli d'Italia", "Italy", "it"),
    # Spain
    "maec.es": ("Ministry of Foreign Affairs", "Spain", "es"),
    "senado.es": ("Senator", "Spain", "es"),
    "congreso.es": ("Member of Congress", "Spain", "es"),
    "presidencia.": ("Presidency", "Spain", "es"),
    "voxespana.es": ("Vox Party", "Spain", "es"),
    "movimientosumar.es": ("Sumar", "Spain", "es"),
    "psoe.es": ("PSOE", "Spain", "es"),
    "pp.es": ("PP", "Spain", "es"),
    # Denmark
    "ft.dk": ("Member of Parliament", "Denmark", "da"),
    "um.dk": ("Ministry of Foreign Affairs", "Denmark", "da"),
    "stm.dk": ("Prime Minister's Office", "Denmark", "da"),
    "socialdemokratiet.dk": ("Social Democrats", "Denmark", "da"),
    "moderaterne.dk": ("Moderaterne", "Denmark", "da"),
    "alternativet.dk": ("Alternativet", "Denmark", "da"),
    # Norway
    "stortinget.no": ("Member of Parliament", "Norway", "no"),
    "smk.dep.no": ("Prime Minister's Office", "Norway", "no"),
    "dep.no": ("Norwegian Government", "Norway", "no"),
    "arbeiderpartiet.no": ("Labour Party", "Norway", "no"),
    "hoyre.no": ("Høyre", "Norway", "no"),
    "sv.no": ("SV", "Norway", "no"),
    "mdg.no": ("MDG", "Norway", "no"),
    "amnesty.no": ("Amnesty International", "Norway", "no"),
    # Austria
    "parlament.gv.at": ("Member of Parliament", "Austria", "de"),
    "bka.gv.at": ("Federal Chancellery", "Austria", "de"),
    "bmeia.gv.at": ("Ministry of Foreign Affairs", "Austria", "de"),
    "oevp.at": ("ÖVP", "Austria", "de"),
    "gruene.at": ("Greens", "Austria", "de"),
    "spoe.at": ("SPÖ", "Austria", "de"),
    "fpoe.at": ("FPÖ", "Austria", "de"),
    "neos.eu": ("NEOS", "Austria", "de"),
    # Netherlands
    "tweedekamer.nl": ("Member of Parliament", "Netherlands", "nl"),
    "minbuza.nl": ("Ministry of Foreign Affairs", "Netherlands", "nl"),
    "d66.nl": ("D66", "Netherlands", "nl"),
    "groenlinkspvda.nl": ("GroenLinks-PvdA", "Netherlands", "nl"),
    "voltnederland.org": ("Volt Netherlands", "Netherlands", "nl"),
    # Hungary
    "me.gov.hu": ("Prime Minister's Office", "Hungary", "hu"),
    "mfa.gov.hu": ("Ministry of Foreign Affairs", "Hungary", "hu"),
    "parlament.hu": ("Member of Parliament", "Hungary", "hu"),
    "keh.hu": ("Presidential Office", "Hungary", "hu"),
    "fidesz.hu": ("Fidesz", "Hungary", "hu"),
    "mszp.hu": ("MSZP", "Hungary", "hu"),
    "momentum.hu": ("Momentum", "Hungary", "hu"),
    # Switzerland
    "parl.admin.ch": ("Member of Parliament", "Switzerland", "de"),
    "eda.admin.ch": ("Ministry of Foreign Affairs", "Switzerland", "de"),
    "admin.ch": ("Swiss Government", "Switzerland", "de"),
    "sp-ps.ch": ("SP", "Switzerland", "de"),
    "fdp.ch": ("FDP", "Switzerland", "de"),
    "die-mitte.ch": ("Die Mitte", "Switzerland", "de"),
    "svp.ch": ("SVP", "Switzerland", "de"),
    "gruene.ch": ("Greens", "Switzerland", "de"),
    # Germany
    "bundestag.de": ("Member of Bundestag", "Germany", "de"),
    "auswaertiges": ("Ministry of Foreign Affairs", "Germany", "de"),
    "cdu.de": ("CDU", "Germany", "de"),
    "csu-landesleitung.de": ("CSU", "Germany", "de"),
    "die-linke.de": ("Die Linke", "Germany", "de"),
    "afd.de": ("AfD", "Germany", "de"),
    "spd.de": ("SPD", "Germany", "de"),
    "gruene.de": ("Greens", "Germany", "de"),
    "fdp.de": ("FDP", "Germany", "de"),
    "cducsu.de": ("CDU/CSU", "Germany", "de"),
    "brüssel.diplo.de": ("German Embassy Brussels", "Germany", "de"),
    "diplo.de": ("German Embassy", "Germany", "de"),
    # International / NGOs
    "fidh.org": ("FIDH", "International", "en"),
    "amnesty.org": ("Amnesty International", "International", "en"),
    "europarl.europa.eu": ("MEP", "EU", "en"),
}

# Local-part keywords → info hint
LOCAL_KEYWORDS: dict[str, str] = {
    "pm": "Prime Minister's Office",
    "premier": "Premier's Office",
    "minister": "Minister",
    "president": "President's Office",
    "senator": "Senator",
    "ambassador": "Ambassador",
    "cabinet": "Cabinet Office",
    "contact": "General Contact",
    "info": "General Contact",
    "press": "Press Office",
    "presse": "Press Office",
    "communication": "Communications",
    "communication": "Communications",
    "questions": "General Contact",
    "courrier": "General Contact",
    "post": "General Contact",
    "facom": "Foreign Affairs Committee",
    "fcdo": "Foreign Affairs",
    "groupe": "Parliamentary Group",
    "fraktion": "Parliamentary Group",
    "fractie": "Parliamentary Group",
    "fraction": "Parliamentary Group",
    "partikontoret": "Party Office",
    "bundespartei": "Federal Party Office",
    "bundesvorstand": "Federal Party Board",
    "parteivorstand": "Party Executive",
    "sekretariat": "Party Secretariat",
    "direktionn": "Party Directorate",
    "direktion": "Party Directorate",
    "audiencias": "Public Audience",
    "sct": "Campaigns",
    "campaigns": "Campaigns",
    "urp": "Press Relations",
    "rpa": "EU Affairs",
    "reper": "EU Representation",
    "dpm": "Deputy Foreign Minister",
    "deza": "Development Cooperation",
    "hrd": "Human Rights Division",
    "speakersoffice": "Speaker's Office",
}


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────


def slug_to_name(slug: str) -> str:
    """'pierre.poilievre' → 'Pierre Poilievre'  (best-effort)"""
    slug = re.sub(r"[._\-]", " ", slug)
    slug = re.sub(r"\s+", " ", slug).strip()
    return slug.title()


def is_personal_email(local: str) -> bool:
    """Heuristic: 'first.last' or 'first_last' looks like a personal address."""
    return bool(re.match(r"^[a-z]{2,}\.[a-z]{2,}$", local, re.I)) or bool(
        re.match(r"^[a-z]{2,}-[a-z]{2,}$", local, re.I)
    )


def tld_from_domain(domain: str) -> str:
    parts = domain.lower().rstrip(".").split(".")
    return parts[-1] if parts else ""


def meta_from_email(email: str) -> dict:
    """
    Purely heuristic, no network call.
    Returns: {local, domain, guessed_name, info_hint, country, language, is_personal}
    """
    email = email.strip()
    if "@" not in email:
        return {}

    local, domain = email.rsplit("@", 1)
    local = local.strip().lower()
    domain = domain.strip().lower()
    tld = tld_from_domain(domain)

    # 1. Domain-keyword lookup (longest match first)
    info_hint = country = language = None
    for fragment in sorted(DOMAIN_HINTS.keys(), key=len, reverse=True):
        if fragment in domain:
            info_hint, country, language = DOMAIN_HINTS[fragment]
            break

    # 2. TLD fallback
    if not country:
        meta = TLD_META.get(tld, ("International", "en", "Organization"))
        country, language = meta[0], meta[1]
        if not info_hint:
            info_hint = meta[2]

    # 3. Override info_hint from local-part keyword
    for kw, desc in LOCAL_KEYWORDS.items():
        if local.startswith(kw) or ("." + kw + ".") in ("." + local + "."):
            info_hint = desc
            break

    # 4. Guess name
    personal = is_personal_email(local)
    if personal:
        guessed_name = slug_to_name(local)
    else:
        guessed_name = info_hint or domain.split(".")[0].title()

    return {
        "local": local,
        "domain": domain,
        "guessed_name": guessed_name,
        "info_hint": info_hint or "Contact",
        "country": country,
        "language": language,
        "is_personal": personal,
    }


def normalize_email(raw: str) -> str | None:
    """Sanitize and validate; returns None for malformed."""
    raw = raw.strip()
    # Remove known broken patterns (spaces inside, trailing dot, etc.)
    raw = re.sub(r"\s+", "", raw)
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", raw):
        log.warning(f"  Skipping malformed email: {raw!r}")
        return None
    return raw


# ──────────────────────────────────────────────────────────────────────────────
# Search helpers
# ──────────────────────────────────────────────────────────────────────────────


def search_ddg(query: str, max_results: int = 5) -> str:
    try:
        import logging as _logging
        from ddgs import DDGS

        # Suppress noisy internal-engine errors from the ddgs library
        _logging.getLogger("ddgs").setLevel(_logging.CRITICAL)
        ddgs = DDGS()
        results = list(ddgs.text(query, max_results=max_results, region="wt-wt"))
        return "\n".join(r.get("body", "") for r in results if r.get("body"))
    except Exception as e:
        log.debug(f"DDG search failed: {e}")
        return ""


def search_tavily(query: str, client, max_results: int = 5) -> str:
    if not client:
        return ""
    try:
        results = client.search(query, max_results=max_results, search_depth="basic")
        return "\n".join(
            r.get("content", "") for r in results.get("results", []) if r.get("content")
        )
    except Exception as e:
        log.debug(f"Tavily search failed: {e}")
        return ""


def web_search(query: str, tavily_client=None, max_results: int = 5) -> str:
    """Try DDG first, fall back to Tavily."""
    snippet = search_ddg(query, max_results)
    if not snippet and tavily_client:
        snippet = search_tavily(query, tavily_client, max_results)
    return snippet


# ──────────────────────────────────────────────────────────────────────────────
# AI extraction
# ──────────────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a political-contact data enrichment assistant.
Given an email address and context clues, extract structured information.
Respond ONLY with valid JSON — no prose, no markdown fences."""

USER_PROMPT_TPL = """Email address: {email}
Heuristic context: country={country}, language={language}, info_hint="{info_hint}", guessed_name="{guessed_name}"
Web search snippet:
---
{snippet}
---

Based on ALL of the above, produce a JSON object with exactly these keys:
  "name"     – Full name of the person or organisation. Title case. If unknown use the organisation/role name.
  "info"     – Role / position / party / organisation (concise, e.g. "Prime Minister Canada", "MEP Greens/EFA", "Labour Party UK", "Media - The Guardian")
  "language" – 2-letter ISO 639-1 code of the language to address this contact in (en, fr, de, sv, it, es, da, no, nl, hu, de, bg, pl, …)

Rules:
- For generic / shared mailboxes (info@, contact@, post@, etc.) use the organisation name as "name".
- The language must match the PRIMARY language spoken in that country / role.
- Do NOT include the email in the output.
- Be concise but accurate.

Example: {{"name": "Melanie Joly", "info": "Minister of Foreign Affairs Canada", "language": "en"}}"""


def ai_extract(email: str, meta: dict, snippet: str, client, model: str) -> dict:
    if not client:
        return {
            "name": meta["guessed_name"],
            "info": meta["info_hint"],
            "language": meta["language"],
        }

    prompt = USER_PROMPT_TPL.format(
        email=email,
        country=meta["country"],
        language=meta["language"],
        info_hint=meta["info_hint"],
        guessed_name=meta["guessed_name"],
        snippet=snippet[:3000] if snippet else "(no search results)",
    )

    for attempt in range(3):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.05,
                max_tokens=200,
            )
            raw = response.choices[0].message.content.strip()
            # Strip markdown code fences if the model adds them anyway
            raw = re.sub(r"^```[a-z]*\n?", "", raw)
            raw = re.sub(r"\n?```$", "", raw)
            extracted = json.loads(raw)
            # Validate keys
            for key in ("name", "info", "language"):
                if key not in extracted:
                    raise ValueError(f"Missing key: {key}")
            return extracted
        except json.JSONDecodeError as e:
            log.debug(f"JSON parse error (attempt {attempt + 1}): {e} — raw={raw!r}")
            time.sleep(1)
        except Exception as e:
            log.debug(f"AI extraction error (attempt {attempt + 1}): {e}")
            time.sleep(2)

    # Final fallback
    return {
        "name": meta["guessed_name"],
        "info": meta["info_hint"],
        "language": meta["language"],
    }


# ──────────────────────────────────────────────────────────────────────────────
# Main converter
# ──────────────────────────────────────────────────────────────────────────────


class EmailCSVConverter:
    def __init__(
        self,
        model: str = "google/gemini-2.5-flash-lite",
        search_personal_only: bool = False,
        no_search: bool = False,
        delay: float = 0.3,
    ):
        self.model = model
        self.search_personal_only = search_personal_only
        self.no_search = no_search
        self.delay = delay

        # OpenRouter
        openrouter_key = os.getenv("OPENROUTER_API_KEY")
        if openrouter_key:
            from openai import OpenAI

            self.ai_client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=openrouter_key,
                default_headers={"HTTP-Referer": "https://github.com/outreach-bot"},
            )
            log.info(f"OpenRouter AI enabled (model: {model})")
        else:
            self.ai_client = None
            log.warning(
                "OPENROUTER_API_KEY not set — AI enrichment disabled, using heuristics only."
            )

        # Tavily
        tavily_key = os.getenv("TAVILY_API_KEY")
        if tavily_key:
            try:
                from tavily import TavilyClient

                self.tavily = TavilyClient(api_key=tavily_key)
                log.info("Tavily search enabled.")
            except ImportError:
                self.tavily = None
        else:
            self.tavily = None
            if not no_search:
                log.info("TAVILY_API_KEY not set — will use DuckDuckGo only.")

    def _build_query(self, email: str, meta: dict) -> str:
        if meta["is_personal"]:
            name_part = meta["guessed_name"]
            return (
                f'"{name_part}" politician OR minister OR senator OR MP OR MEP '
                f"{meta['country']} language OR party OR role site:wikipedia.org OR site:parliament.{tld_from_domain(meta['domain'])}"
            )
        else:
            # Generic mailbox — search for the organisation
            org = meta["domain"].split(".")[0]
            return f"{org} {meta['country']} official role language"

    def process_email(self, email: str) -> dict | None:
        email = normalize_email(email)
        if not email:
            return None

        meta = meta_from_email(email)
        if not meta:
            return None

        snippet = ""
        if not self.no_search:
            if not self.search_personal_only or meta["is_personal"]:
                query = self._build_query(email, meta)
                log.debug(f"  Search: {query}")
                snippet = web_search(query, self.tavily, max_results=5)

        extracted = ai_extract(email, meta, snippet, self.ai_client, self.model)

        time.sleep(self.delay)

        return {
            "name": extracted.get("name", meta["guessed_name"]).strip(),
            "email": email,
            "info": extracted.get("info", meta["info_hint"]).strip(),
            "language": extracted.get("language", meta["language"]).strip().lower()[:2],
        }

    def convert(self, input_path: str, output_path: str) -> None:
        input_path = Path(input_path)
        if not input_path.exists():
            log.error(f"Input file not found: {input_path}")
            sys.exit(1)

        # ── Read input ──────────────────────────────────────────────────────
        # Accept: single-column CSV (with or without header), or plain text
        raw_text = input_path.read_text(
            encoding="utf-8-sig", errors="replace"
        )  # utf-8-sig strips BOM
        lines = [l.strip() for l in raw_text.splitlines() if l.strip()]

        # If first line looks like a header (no @), skip it
        if lines and "@" not in lines[0]:
            log.info(f"Skipping header line: {lines[0]!r}")
            lines = lines[1:]

        # Strip surrounding quotes / CSV commas
        emails_raw = []
        for line in lines:
            # Handle possible CSV format: take the first column
            cols = line.split(",")
            candidate = cols[0].strip().strip('"').strip("'")
            if candidate:
                emails_raw.append(candidate)

        log.info(f"Found {len(emails_raw)} email entries in {input_path.name}")

        # ── Process ─────────────────────────────────────────────────────────
        results = []
        skipped = 0
        for raw_email in tqdm(emails_raw, desc="Processing emails", unit="email"):
            row = self.process_email(raw_email)
            if row:
                results.append(row)
            else:
                skipped += 1

        # ── Write output ────────────────────────────────────────────────────
        if not results:
            log.error("No valid results to write.")
            sys.exit(1)

        df = pd.DataFrame(results, columns=["name", "email", "info", "language"])
        df.to_csv(output_path, index=False, encoding="utf-8")
        log.info(f"✅ Wrote {len(results)} rows to {output_path}  (skipped: {skipped})")
        print(f"\nDone! Output: {output_path}")
        print(df.head(10).to_string(index=False))


# ──────────────────────────────────────────────────────────────────────────────
# CLI entry-point
# ──────────────────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="Convert a flat email-list CSV to sample_draft.csv format.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python convert_emails_csv.py emails.csv
  python convert_emails_csv.py emails.csv output.csv
  python convert_emails_csv.py emails.csv --model meta-llama/llama-3.3-70b-instruct
  python convert_emails_csv.py emails.csv --no-search       # heuristics only, no web search
  python convert_emails_csv.py emails.csv --delay 0.5
""",
    )
    parser.add_argument("input", help="Input CSV file (one email per row)")
    parser.add_argument(
        "output",
        nargs="?",
        default="sample_draft.csv",
        help="Output CSV file (default: sample_draft.csv)",
    )
    parser.add_argument(
        "--model",
        default="openai/gpt-4o-mini",
        help="OpenRouter model ID (default: openai/gpt-4o-mini)",
    )
    parser.add_argument(
        "--no-search",
        action="store_true",
        help="Skip web search; rely on heuristics + AI knowledge only",
    )
    parser.add_argument(
        "--personal-only",
        action="store_true",
        help="Only web-search personal (first.last) email addresses",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.3,
        help="Seconds between API calls (default: 0.3)",
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    converter = EmailCSVConverter(
        model=args.model,
        search_personal_only=args.personal_only,
        no_search=args.no_search,
        delay=args.delay,
    )
    converter.convert(args.input, args.output)


if __name__ == "__main__":
    main()
