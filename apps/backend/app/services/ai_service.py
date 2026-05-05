import json
import logging
from typing import List, Dict, Optional

from openai import OpenAI
from sqlalchemy.orm import Session

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

CATEGORIES = [
    "IA",
    "Negócios",
    "Tecnologia",
    "Política",
    "Economia",
    "Saúde",
    "Produtividade",
    "Marketing",
    "Filosofia",
    "Outros",
]


def _resolve_openai_key(db: Optional[Session]) -> str:
    if db is not None:
        try:
            from app.services.settings_service import SettingsService
            val = SettingsService(db).get_value("openai_api_key")
            if val:
                return val
        except Exception:
            pass
    return settings.OPENAI_API_KEY


class AIService:
    def __init__(self, db: Optional[Session] = None) -> None:
        api_key = _resolve_openai_key(db)
        self.client = OpenAI(api_key=api_key)

    def analyze_content(
        self,
        content_type: str,
        raw_text: Optional[str] = None,
        url: Optional[str] = None,
        extracted_text: Optional[str] = None,
        page_title: Optional[str] = None,
        page_description: Optional[str] = None,
        transcript: Optional[str] = None,
    ) -> Dict:
        """Analyse content with OpenAI and return structured metadata."""
        context_parts = []

        if content_type == "link":
            if page_title:
                context_parts.append(f"Page Title: {page_title}")
            if page_description:
                context_parts.append(f"Page Description: {page_description}")

        if transcript:
            context_parts.append(f"Audio Transcript: {transcript[:12000]}")
        if extracted_text:
            context_parts.append(f"Extracted Content (OCR): {extracted_text[:12000]}")
        elif raw_text:
            context_parts.append(f"Raw Text: {raw_text[:12000]}")

        if url:
            context_parts.append(f"URL: {url}")

        context = "\n\n".join(context_parts)

        prompt = f"""You are an intelligent content analyzer. Analyze the following content and provide structured metadata.

Content Type: {content_type}

{context}

Available Categories: {', '.join(CATEGORIES)}

Analyze this content and return a JSON object with the following structure:
{{
    "title": "A concise, descriptive title (max 100 chars)",
    "summary": "A brief summary of the key points (max 300 chars)",
    "category": "One of the available categories listed above",
    "tags": ["tag1", "tag2", "tag3"],
    "importance_score": 0-10,
    "actionable": true/false
}}

Guidelines:
- Title should be descriptive and concise
- Summary should capture the main insights
- Category must be exactly one from the available list
- Tags should be 3-5 relevant keywords (lowercase, no spaces)
- Importance score: 0-10 based on novelty, usefulness, and relevance
- Actionable: true if the content suggests actions, tasks, or decisions

Return ONLY the JSON object, no other text."""

        try:
            response = self.client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": "You are a precise content analyzer. Always return valid JSON."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=500,
                response_format={"type": "json_object"},
            )

            result = json.loads(response.choices[0].message.content)

            result["category"] = result.get("category", "Outros")
            if result["category"] not in CATEGORIES:
                result["category"] = "Outros"

            result["tags"] = result.get("tags", [])[:10]
            result["importance_score"] = max(0, min(10, result.get("importance_score", 5)))
            result["actionable"] = bool(result.get("actionable", False))

            return result

        except Exception as exc:
            logger.warning("AI analysis failed, using fallback: %s", exc)
            return {
                "title": page_title or (raw_text[:100] if raw_text else "Untitled"),
                "summary": raw_text[:300] if raw_text else "",
                "category": "Outros",
                "tags": [],
                "importance_score": 5,
                "actionable": False,
                "error": str(exc),
            }

    def generate_embedding(self, text: str) -> List[float]:
        """Generate a 1536-dimension embedding vector."""
        try:
            response = self.client.embeddings.create(
                model=settings.OPENAI_EMBEDDING_MODEL,
                input=text[:8000],
            )
            return response.data[0].embedding
        except Exception as exc:
            logger.warning("Embedding generation failed, returning zero vector: %s", exc)
            return [0.0] * 1536

    def summarize_text(self, text: str, max_length: int = 300) -> str:
        """Generate a short summary of text."""
        try:
            response = self.client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": "Summarize the following text concisely."},
                    {"role": "user", "content": f"Summarize this in {max_length} characters or less:\n\n{text[:12000]}"},
                ],
                temperature=0.3,
                max_tokens=200,
            )
            return response.choices[0].message.content.strip()
        except Exception as exc:
            logger.warning("Summarization failed: %s", exc)
            return text[:max_length] if text else ""
