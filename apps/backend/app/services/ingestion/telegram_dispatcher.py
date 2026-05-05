"""Command dispatcher for Telegram bot messages.

Intercepts messages that start with '/' and returns a reply string.
Returns None for regular content that should pass through to the ingestion pipeline.
"""
from typing import Optional
from sqlalchemy.orm import Session


async def dispatch(text: str, chat_id: int, db: Session) -> Optional[str]:
    """Return a reply string if text is a bot command, else None."""
    stripped = (text or "").strip()
    # Strip /command@BotName format
    if stripped.startswith("/"):
        stripped = stripped.split("@")[0] + (f" {stripped.split(None, 1)[1]}" if len(stripped.split(None, 1)) > 1 else "")
    if not stripped.startswith("/"):
        return None

    parts = stripped.split(None, 1)
    cmd = parts[0].lower()
    args = parts[1].strip() if len(parts) > 1 else ""

    if cmd == "/help" or cmd == "/start":
        return (
            "🤖 Comandos disponíveis:\n\n"
            "/status — status da integração\n"
            "/search <busca> — pesquisar no vault\n"
            "/help — esta mensagem\n\n"
            "Qualquer outra mensagem é capturada e processada pela IA."
        )

    if cmd == "/status":
        return await _status(db)

    if cmd == "/search":
        if not args:
            return "Uso: /search <sua busca>"
        return await _search(args, db)

    return f"Comando desconhecido: {cmd}\nDigite /help para ver os comandos disponíveis."


async def _status(db: Session) -> str:
    from app.services.settings_service import SettingsService
    from app.core.config import get_settings
    env = get_settings()
    svc = SettingsService(db)

    has_openai = bool(svc.get_runtime_value("openai_api_key", env.OPENAI_API_KEY))
    has_tg = bool(svc.get_runtime_value("telegram_bot_token", env.TELEGRAM_BOT_TOKEN))

    lines = ["⚙️ Status do Keepiu\n"]
    lines.append(f"OpenAI: {'✅ configurado' if has_openai else '❌ não configurado'}")
    lines.append(f"Telegram: {'✅ configurado' if has_tg else '❌ não configurado'}")
    lines.append(f"Modo: {env.APP_MODE}")
    lines.append(f"Processamento: {env.PROCESSING_MODE}")
    return "\n".join(lines)


async def _search(query: str, db: Session) -> str:
    try:
        from app.services.ai_service import AIService
        from app.models.content import Content, ContentEmbedding
        ai = AIService()
        embedding = ai.generate_embedding(query)
        rows = (
            db.query(Content.title, Content.raw_text)
            .join(ContentEmbedding, Content.id == ContentEmbedding.content_id)
            .order_by(ContentEmbedding.vector.l2_distance(embedding))
            .limit(5)
            .all()
        )
        if not rows:
            return f"Nenhum resultado encontrado para: {query}"
        lines = [f"🔍 Resultados para {query}:\n"]
        for i, row in enumerate(rows, 1):
            label = row.title or (row.raw_text or "")[:60]
            lines.append(f"{i}. {label}")
        return "\n".join(lines)
    except Exception:
        return "Erro ao realizar a busca. Verifique se o OpenAI está configurado."
