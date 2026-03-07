import openai
from typing import Dict, Any
from config import Config

class OpenRouterService:
    def __init__(self):
        self.client = openai.AsyncOpenAI(
            api_key=Config.OPENROUTER_API_KEY,
            base_url=Config.OPENROUTER_BASE_URL,
        )
        self.model = Config.OPENROUTER_MODEL
        self.fallback_model = Config.FALLBACK_MODEL

    async def generate_email(self, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        """Generate subject and body using OpenRouter"""
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
                max_tokens=500,
            )
            content = response.choices[0].message.content.strip()
            # Parse subject and body (assume format: Subject: ...\n\nBody: ...)
            if 'Subject:' in content and 'Body:' in content:
                subject = content.split('Subject:')[1].split('\n\nBody:')[0].strip()
                body = content.split('Body:')[1].strip()
                return {"subject": subject, "body": body}
            else:
                # Fallback parse - handle Bulgarian "Относно:" / "Тяло:"
                lines = content.split('\n')
                if lines:
                    first_line = lines[0].strip()
                    if first_line.startswith('Относно:') or first_line.startswith('Subject:'):
                        subject = first_line.split(':', 1)[1].strip()
                        body = '\n'.join(lines[1:]).strip()
                    else:
                        subject = first_line or "Formal Request"
                        body = '\n'.join(lines[1:]).strip()
                    return {"subject": subject, "body": body}
                return {"subject": "Formal Request", "body": ""}
        except Exception as e:
            # Fallback model
            try:
                response = await self.client.chat.completions.create(
                    model=self.fallback_model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.3,
                    max_tokens=500,
                )
                content = response.choices[0].message.content.strip()
                lines = content.split('\n')
                if lines:
                    first_line = lines[0].strip()
                    if first_line.startswith('Относно:') or first_line.startswith('Subject:'):
                        subject = first_line.split(':', 1)[1].strip()
                        body = '\n'.join(lines[1:]).strip()
                    else:
                        subject = first_line or "Formal Request"
                        body = '\n'.join(lines[1:]).strip()
                    return {"subject": subject, "body": body}
                return {"subject": "Formal Request", "body": ""}
            except Exception:
                raise ValueError(f"Failed to generate email: {str(e)}")