"""
Instagram AI Service — OpenAI analysis specifically for Instagram posts.

Returns structured JSON with: summary, tone, niche, cta, tags,
language_detected, and sentiment_score.
"""
import json
import logging
from typing import Optional

from openai import OpenAI
from sqlalchemy.orm import Session

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_PROMPT_TEMPLATE = """\
Analise os dados abaixo de um post do Instagram.

Considere:
- legenda (caption)
- texto detectado nas imagens (OCR)
- metadados disponíveis

Dados do post:
{context}

Retorne um JSON com exatamente este formato (sem texto adicional):

{{
  "summary": "resumo claro e objetivo do post (max 300 chars)",
  "tone": "tom da comunicação (ex: motivacional, informativo, promocional, humorístico, emocional)",
  "niche": "nicho provável do conteúdo (ex: fitness, moda, tecnologia, gastronomia, negócios)",
  "cta": "call to action identificado no post ou vazio se não houver",
  "tags": ["tag1", "tag2", "tag3", "tag4", "tag5"],
  "language_detected": "código ISO do idioma dominante (ex: pt-BR, en-US, es)",
  "sentiment_score": 0.82
}}

Regras:
- sentiment_score: float de 0.0 (muito negativo) a 1.0 (muito positivo)
- tags: 3 a 6 palavras-chave relevantes, minúsculas, sem espaços
- Se caption for vazio e OCR for vazio, baseie-se no contexto disponível
"""


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


class InstagramAIService:
    def __init__(self, db: Optional[Session] = None) -> None:
        api_key = _resolve_openai_key(db)
        self.client = OpenAI(api_key=api_key)

    def analyze(
        self,
        caption: Optional[str],
        ocr_texts: list[str],
        username: Optional[str] = None,
        media_type: Optional[str] = None,
        permalink: Optional[str] = None,
        slide_count: int = 1,
    ) -> dict:
        """
        Analyse an Instagram post and return structured metadata.
        Supports carousels — each slide's OCR text is presented in order.
        Falls back gracefully when OpenAI is unavailable.
        """
        context_parts = []

        if caption:
            context_parts.append(f"Legenda: {caption[:2000]}")
        else:
            context_parts.append("Legenda: (não disponível)")

        if len(ocr_texts) > 1:
            # Carousel: present each slide's text with its index
            context_parts.append(f"Carrossel com {slide_count} slides:")
            for i, text in enumerate(ocr_texts):
                context_parts.append(f"  Slide {i + 1}: {text[:500]}")
        elif ocr_texts:
            combined_ocr = ocr_texts[0].strip()
            if combined_ocr:
                context_parts.append(f"Texto detectado por OCR: {combined_ocr[:2000]}")

        if username:
            context_parts.append(f"Autor: @{username}")
        if media_type:
            context_parts.append(f"Tipo de mídia: {media_type}")
        if permalink:
            context_parts.append(f"Link: {permalink}")

        context = "\n".join(context_parts)
        prompt = _PROMPT_TEMPLATE.format(context=context)

        try:
            response = self.client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Você é um especialista em análise de conteúdo de redes sociais. "
                            "Retorne sempre JSON válido conforme solicitado."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=600,
                response_format={"type": "json_object"},
            )

            result = json.loads(response.choices[0].message.content)
            return _sanitize(result, caption, combined_ocr)

        except Exception as exc:
            logger.warning("Instagram AI analysis failed, using fallback: %s", exc)
            return _fallback(caption, combined_ocr, str(exc))


def _sanitize(result: dict, caption: Optional[str], ocr: str) -> dict:
    """Ensure all required keys are present and within bounds."""
    fallback_text = caption or ocr or "Post do Instagram"
    return {
        "summary": (result.get("summary") or fallback_text[:300]),
        "tone": result.get("tone") or "informativo",
        "niche": result.get("niche") or "geral",
        "cta": result.get("cta") or "",
        "tags": [str(t).lower().replace(" ", "-") for t in result.get("tags", [])][:6],
        "language_detected": result.get("language_detected") or "pt-BR",
        "sentiment_score": max(0.0, min(1.0, float(result.get("sentiment_score", 0.5)))),
    }


def _fallback(caption: Optional[str], ocr: str, error: str) -> dict:
    text = caption or ocr or "Post do Instagram"
    return {
        "summary": text[:300],
        "tone": "informativo",
        "niche": "geral",
        "cta": "",
        "tags": [],
        "language_detected": "pt-BR",
        "sentiment_score": 0.5,
        "error": error,
    }
