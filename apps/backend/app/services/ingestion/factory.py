from app.services.ingestion.telegram_normalizer import TelegramNormalizer
from app.services.ingestion.whatsapp_normalizer import WhatsAppNormalizer


def get_normalizer(channel: str):
    if channel == "telegram":
        return TelegramNormalizer()
    if channel == "whatsapp":
        return WhatsAppNormalizer()
    raise ValueError(f"Unknown ingestion channel: {channel!r}")
