import json
import logging
import openai
from typing import Dict, Any, Optional
from config import Config

logger = logging.getLogger(__name__)

# ── Tool schemas ──────────────────────────────────────────────────────────────

_EMAIL_TOOL = {
    "type": "function",
    "function": {
        "name": "generate_email",
        "description": "Return the generated formal email with subject and full body.",
        "parameters": {
            "type": "object",
            "properties": {
                "subject": {
                    "type": "string",
                    "description": "The email subject line — compelling, relevant to the recipient."
                },
                "body": {
                    "type": "string",
                    "description": "Full email body text, formatted as a plain-text formal letter."
                }
            },
            "required": ["subject", "body"]
        }
    }
}

_PROFILE_TOOL = {
    "type": "function",
    "function": {
        "name": "extract_profile",
        "description": "Extract a structured political profile from search text.",
        "parameters": {
            "type": "object",
            "properties": {
                "bio":      {"type": "string", "description": "200-word biography summary"},
                "gender":   {"type": "string", "enum": ["male", "female", "unknown"]},
                "targets":  {"type": "array",  "items": {"type": "string"}, "description": "Political targets/goals"},
                "mottos":   {"type": "array",  "items": {"type": "string"}, "description": "Election mottos and slogans"},
                "values":   {"type": "array",  "items": {"type": "string"}, "description": "Core values"},
                "keywords": {"type": "array",  "items": {"type": "string"}, "description": "Top 10 keywords"},
                "subjects": {"type": "array",  "items": {"type": "string"}, "description": "Repetitive speech topics/subjects"}
            },
            "required": ["bio", "gender", "targets", "mottos", "values", "keywords", "subjects"]
        }
    }
}

# ── Output validators ─────────────────────────────────────────────────────────

# Substrings that indicate the model returned a template instead of real content
_PLACEHOLDER_PATTERNS = (
    '[', 'insert', 'your name', 'your email',
    'subject here', 'body here', 'write here', 'add here',
)

def _is_valid_email(subject: str, body: str) -> bool:
    """
    Return True only if subject and body look like real generated content.
    Rejects empty output, placeholder text, and suspiciously short responses.
    """
    s = subject.strip()
    b = body.strip()
    if len(s) < 5 or len(s) > 150:
        return False
    if len(b) < 50:
        return False
    lower_s, lower_b = s.lower(), b.lower()
    for pat in _PLACEHOLDER_PATTERNS:
        if pat in lower_s or pat in lower_b:
            return False
    return True


# ── Fallback text parsers (used when a model doesn't support tool_choice) ─────

def _parse_email_from_text(content: str) -> Dict[str, str]:
    """Best-effort parse of 'Subject: ...\n\nBody: ...' style text."""
    if 'Subject:' in content and 'Body:' in content:
        subject = content.split('Subject:')[1].split('\n\nBody:')[0].strip()
        body = content.split('Body:')[1].strip()
        return {"subject": subject, "body": body}
    # Handle Bulgarian / other locale headers
    lines = content.split('\n')
    if lines:
        first = lines[0].strip()
        if ':' in first and len(first) < 200:  # looks like a header line
            subject = first.split(':', 1)[1].strip()
            body = '\n'.join(lines[1:]).strip()
        else:
            subject = first or "Formal Request"
            body = '\n'.join(lines[1:]).strip()
        return {"subject": subject, "body": body}
    return {"subject": "Formal Request", "body": content}


_EMPTY_PROFILE: Dict[str, Any] = {
    "bio": "", "gender": "unknown",
    "targets": [], "mottos": [], "values": [], "keywords": [], "subjects": []
}


class OpenRouterService:
    def __init__(self):
        self.client = openai.AsyncOpenAI(
            api_key=Config.OPENROUTER_API_KEY,
            base_url=Config.OPENROUTER_BASE_URL,
        )
        self.model = Config.OPENROUTER_MODEL
        self.fallback_model = Config.FALLBACK_MODEL

    # ── Internal helpers ──────────────────────────────────────────────────────

    async def _call_with_tool(
        self,
        model: str,
        messages: list,
        tool: dict,
        temperature: float = 0.3,
        max_tokens: int = 700,
    ) -> Optional[Dict]:
        """
        Try a single tool-call completion.
        Returns the parsed dict from tool_calls[0].function.arguments, or None.
        """
        try:
            response = await self.client.chat.completions.create(
                model=model,
                messages=messages,
                tools=[tool],
                tool_choice={"type": "function", "name": tool["function"]["name"]},
                temperature=temperature,
                max_tokens=max_tokens,
            )
            msg = response.choices[0].message
            if msg.tool_calls:
                return json.loads(msg.tool_calls[0].function.arguments)
        except Exception as exc:
            logger.debug(f"Tool call failed on {model}: {exc}")
        return None

    async def _call_plain(
        self,
        model: str,
        messages: list,
        temperature: float = 0.3,
        max_tokens: int = 700,
    ) -> str:
        """Plain text completion — returns raw content string."""
        response = await self.client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content.strip()

    # ── Public API ────────────────────────────────────────────────────────────

    async def generate_email(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str = None,
    ) -> Dict[str, str]:
        """
        Generate subject + body for an outreach email.

        Strategy:
          1. Try primary model with tool_choice (structured output — most reliable)
          2. If tool call fails, try primary model with plain completion + text parse
          3. If that fails, repeat with fallback model
        """
        active_model = model or self.model
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ]

        # ① Primary model — structured tool call
        result = await self._call_with_tool(active_model, messages, _EMAIL_TOOL)
        if result:
            subj, body = result.get("subject", ""), result.get("body", "")
            if _is_valid_email(subj, body):
                logger.debug(f"Email generated via tool call on {active_model}")
                return result
            logger.warning(f"Tool call on {active_model} returned invalid output (subject={repr(subj[:40])}, body_len={len(body)})")

        # ② Primary model — plain text fallback
        try:
            content = await self._call_plain(active_model, messages)
            parsed = _parse_email_from_text(content)
            if _is_valid_email(parsed["subject"], parsed["body"]):
                logger.debug(f"Email generated via text parse on {active_model}")
                return parsed
            logger.warning(f"Plain call on {active_model} returned invalid output")
        except Exception as e:
            logger.warning(f"Plain call failed on {active_model}: {e}")

        # ③ Fallback model — structured tool call
        result = await self._call_with_tool(self.fallback_model, messages, _EMAIL_TOOL)
        if result:
            subj, body = result.get("subject", ""), result.get("body", "")
            if _is_valid_email(subj, body):
                logger.debug(f"Email generated via tool call on fallback {self.fallback_model}")
                return result
            logger.warning(f"Tool call on fallback {self.fallback_model} returned invalid output")

        # ④ Fallback model — plain text
        try:
            content = await self._call_plain(self.fallback_model, messages)
            parsed = _parse_email_from_text(content)
            if _is_valid_email(parsed["subject"], parsed["body"]):
                logger.debug(f"Email generated via text parse on fallback {self.fallback_model}")
                return parsed
        except Exception as e:
            logger.warning(f"Plain call on fallback {self.fallback_model} failed: {e}")

        raise ValueError(
            f"All 4 generation attempts returned empty or invalid output "
            f"(primary={active_model}, fallback={self.fallback_model})"
        )

    async def extract_profile(
        self,
        search_text: str,
        model: str = None,
    ) -> Dict[str, Any]:
        """
        Extract a structured political profile from raw search text.

        Strategy: same 4-step cascade as generate_email but with _PROFILE_TOOL.
        Returns a dict matching _EMPTY_PROFILE structure (never raises).
        """
        active_model = model or self.model
        system = "You are a political research assistant. Extract structured profile data. Respond only via the tool."
        user = f"""Extract a political profile from the following search results.

Search text:
{search_text[:4000]}"""
        messages = [
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ]

        # ① Primary — structured
        result = await self._call_with_tool(active_model, messages, _PROFILE_TOOL, max_tokens=800)
        if result:
            logger.debug(f"Profile extracted via tool call on {active_model}")
            return {**_EMPTY_PROFILE, **result}  # fill missing keys with defaults

        # ② Primary — JSON from plain text
        try:
            content = await self._call_plain(active_model, messages, max_tokens=800)
            # The model may return raw JSON with or without markdown fencing
            clean = content.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            profile = json.loads(clean)
            logger.debug(f"Profile extracted via JSON parse on {active_model}")
            return {**_EMPTY_PROFILE, **profile}
        except Exception as e:
            logger.warning(f"Profile plain parse failed on {active_model}: {e}")

        # ③ Fallback — structured
        result = await self._call_with_tool(self.fallback_model, messages, _PROFILE_TOOL, max_tokens=800)
        if result:
            return {**_EMPTY_PROFILE, **result}

        # ④ Fallback — JSON from plain text
        try:
            content = await self._call_plain(self.fallback_model, messages, max_tokens=800)
            clean = content.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            return {**_EMPTY_PROFILE, **json.loads(clean)}
        except Exception:
            pass

        # All attempts failed — return safe empty profile
        logger.error("Profile extraction completely failed, returning empty profile")
        return dict(_EMPTY_PROFILE)
