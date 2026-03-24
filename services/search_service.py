import json
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from ddgs import DDGS
from tavily import TavilyClient
from database.db import RecipientInfo
from services.openrouter_service import OpenRouterService
from config import Config


class SearchService:
    CACHE_DAYS = 30

    def __init__(self):
        # NOTE: Do NOT store a shared DDGS() instance here.
        # DDGS is not thread-safe; create a fresh one per search call.
        self.tavily_api_key = Config.TAVILY_API_KEY
        self.ors = OpenRouterService()

    def _ddg_search(self, query: str, lang: str) -> str:
        """
        Blocking DDG search — called via asyncio.to_thread.
        Creates a fresh DDGS instance per call to ensure thread-safety.
        """
        try:
            ddg = DDGS()
            results = ddg.text(query, lang=lang, max_results=10)
            return "\n".join([r["body"] for r in (results or [])[:5]])
        except Exception:
            return ""

    def _tavily_search(self, query: str) -> str:
        """
        Blocking Tavily search — called via asyncio.to_thread.
        Creates a fresh TavilyClient per call to ensure thread-safety.
        """
        try:
            client = TavilyClient(api_key=self.tavily_api_key)
            results = client.search(query, max_results=5)
            return "\n".join([r["content"] for r in results.get("results", [])])
        except Exception:
            return ""

    async def get_recipient_profile(
        self, session: AsyncSession, rec: Dict[str, str]
    ) -> Dict[str, Any]:
        email = rec["email"]
        lang = rec["language"]

        # Check cache
        recipient = await session.get(RecipientInfo, email)
        if recipient and recipient.last_searched > datetime.utcnow() - timedelta(
            days=self.CACHE_DAYS
        ):
            return json.loads(recipient.profile_json) if recipient.profile_json else {}

        # Build search query
        name = rec["name"]
        info = rec["info"]
        query = f'"{name}" politician "{info}" biography targets mottos values keywords election campaign'

        # Primary: DDG (fresh instance per call — thread-safe)
        search_text = await asyncio.to_thread(self._ddg_search, query, lang)

        # Fallback: Tavily
        if not search_text and self.tavily_api_key:
            search_text = await asyncio.to_thread(self._tavily_search, query)

        if not search_text:
            profile = {
                "bio": "",
                "gender": "unknown",
                "targets": [],
                "mottos": [],
                "values": [],
                "keywords": [],
                "subjects": [],
            }
        else:
            # Use dedicated structured profile extractor (tool/function calling)
            profile = await self.ors.extract_profile(search_text)

        # Save/update cache
        profile_json = json.dumps(profile)
        if recipient:
            recipient.profile_json = profile_json
            recipient.last_searched = datetime.utcnow()
            recipient.language = lang
        else:
            recipient = RecipientInfo(
                email=email,
                profile_json=profile_json,
                language=lang,
                last_searched=datetime.utcnow(),
            )
            session.add(recipient)
        await session.commit()

        return profile
