from typing import Dict, Any, Optional
from config import Config
from services.openrouter_service import OpenRouterService
from utils.user_settings import get_user_model

class EmailGenerator:
    def __init__(self):
        self.openrouter = OpenRouterService()

    async def generate_personalized_email(self, context: str, name: str, info: str, lang: str, sender_name: str, profile: Dict[str, Any] = None, chat_id: int = None) -> Dict[str, str]:
        """
        Generate personalized formal email for politician using profile.
        """
        system_prompt = Config.get_system_prompt(lang)
        
        # Extract last name for salutation
        last_name = name.split()[-1] if name.split() else name
        
        user_prompt = f"""Campaign context/goal: {context}

Recipient details:
- Full name: {name}
- Position/Party/Info: {info}
- Language: {lang}
- Sender name (use EXACTLY in closing): {sender_name}"""

        if profile:
            user_prompt += f"""

Recipient profile from research:
Bio: {profile.get('bio', '')}
Gender: {profile.get('gender', 'unknown')}
Targets: {', '.join(profile.get('targets', []))}
Mottos: {', '.join(profile.get('mottos', []))}
Values: {', '.join(profile.get('values', []))}
Keywords: {', '.join(profile.get('keywords', []))}
Subjects: {', '.join(profile.get('subjects', []))}

Use profile for hyper-personalization. Match language/style. Official clickbait subjects using keywords/mottos."""

        user_prompt += """

Generate a personalized email using the exact structure from system prompt. Use the sender name exactly in the closing signature, no placeholders."""

        # Resolve per-user model if chat_id is provided
        model_override = get_user_model(chat_id) if chat_id is not None else None
        email_data = await self.openrouter.generate_email(system_prompt, user_prompt, model=model_override)
        return email_data
