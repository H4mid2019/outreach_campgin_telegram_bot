import json
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from ddgs import DDGS
from tavily import TavilyClient
from database.db import RecipientInfo, AsyncSessionLocal, engine
from services.openrouter_service import OpenRouterService
from config import Config

class SearchService:
    CACHE_DAYS = 30

    def __init__(self):
        self.ddg = DDGS()
        self.tavily = TavilyClient(api_key=Config.TAVILY_API_KEY) if Config.TAVILY_API_KEY else None
        self.ors = OpenRouterService()

    async def get_recipient_profile(self, session: AsyncSession, rec: Dict[str, str]) -> Dict[str, Any]:
        email = rec['email']
        lang = rec['language']
        
        # Check cache
        recipient = await session.get(RecipientInfo, email)
        if recipient and recipient.last_searched > datetime.utcnow() - timedelta(days=self.CACHE_DAYS):
            return json.loads(recipient.profile_json) if recipient.profile_json else {}
        
        # Search
        name = rec['name']
        info = rec['info']
        query = f'"{name}" politician "{info}" biography targets mottos values keywords election campaign'
        
        try:
            # Primary DDG
            ddg_results = await asyncio.to_thread(self.ddg.text, query, lang=lang, max_results=10)
            search_text = '\n'.join([r['body'] for r in ddg_results[:5]])
        except:
            search_text = ''
        
        if not search_text and self.tavily:
            # Fallback Tavily
            tavily_results = await asyncio.to_thread(self.tavily.search, query, max_results=5)
            search_text = '\n'.join([r['content'] for r in tavily_results['results']])
        
        if not search_text:
            profile = {'bio': '', 'gender': 'unknown', 'targets': [], 'mottos': [], 'values': [], 'keywords': [], 'subjects': []}
        else:
            # LLM extract
            extract_prompt = f"""Extract political profile from search text. Output JSON only.

Text: {search_text[:4000]}

JSON schema:
{{
  "bio": "200 word summary",
  "gender": "male|female|unknown",
  "targets": ["list of targets"],
  "mottos": ["election mottos/slogans"],
  "values": ["core values"],
  "keywords": ["top 10 keywords"],
  "subjects": ["repetitive titles/subjects"]
}}"""
            response = await self.ors.generate_email("JSON extractor. Respond JSON only.", extract_prompt)
            try:
                profile = json.loads(response['body'])
            except:
                profile = {'bio': search_text[:500], 'gender': 'unknown', 'targets': [], 'mottos': [], 'values': [], 'keywords': [], 'subjects': []}
        
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
                last_searched=datetime.utcnow()
            )
            session.add(recipient)
        await session.commit()
        
        return profile