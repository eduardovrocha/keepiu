"""Unit tests for AIService — OpenAI client is fully mocked."""
from unittest.mock import MagicMock, patch
import pytest

from app.services.ai_service import AIService, CATEGORIES


@pytest.fixture
def ai_service():
    with patch("app.services.ai_service.OpenAI") as mock_openai_cls:
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        svc = AIService()
        svc._mock_client = mock_client
        yield svc


def _make_completion_response(content: str):
    mock_response = MagicMock()
    mock_response.choices[0].message.content = content
    return mock_response


def _make_embedding_response(vector: list):
    mock_response = MagicMock()
    mock_response.data[0].embedding = vector
    return mock_response


class TestAnalyzeContent:
    def test_returns_expected_keys(self, ai_service):
        ai_service._mock_client.chat.completions.create.return_value = (
            _make_completion_response(
                '{"title":"T","summary":"S","category":"IA","tags":["a"],'
                '"importance_score":7,"actionable":false}'
            )
        )
        result = ai_service.analyze_content("text", raw_text="hello AI")
        assert {"title", "summary", "category", "tags", "importance_score", "actionable"} <= result.keys()

    def test_clamps_importance_score(self, ai_service):
        ai_service._mock_client.chat.completions.create.return_value = (
            _make_completion_response(
                '{"title":"T","summary":"S","category":"IA","tags":[],'
                '"importance_score":999,"actionable":false}'
            )
        )
        result = ai_service.analyze_content("text", raw_text="x")
        assert result["importance_score"] == 10

    def test_unknown_category_falls_back(self, ai_service):
        ai_service._mock_client.chat.completions.create.return_value = (
            _make_completion_response(
                '{"title":"T","summary":"S","category":"Unknown XYZ","tags":[],'
                '"importance_score":5,"actionable":false}'
            )
        )
        result = ai_service.analyze_content("text", raw_text="x")
        assert result["category"] == "Outros"

    def test_api_error_returns_fallback(self, ai_service):
        ai_service._mock_client.chat.completions.create.side_effect = RuntimeError("API down")
        result = ai_service.analyze_content("text", raw_text="fallback text")

        assert result["category"] == "Outros"
        assert result["importance_score"] == 5
        assert "error" in result

    def test_limits_tags_to_10(self, ai_service):
        tags = [f"tag{i}" for i in range(20)]
        ai_service._mock_client.chat.completions.create.return_value = (
            _make_completion_response(
                f'{{"title":"T","summary":"S","category":"IA","tags":{tags},'
                f'"importance_score":5,"actionable":false}}'
            )
        )
        result = ai_service.analyze_content("text", raw_text="x")
        assert len(result["tags"]) <= 10


class TestGenerateEmbedding:
    def test_returns_1536_floats(self, ai_service):
        vector = [0.1] * 1536
        ai_service._mock_client.embeddings.create.return_value = (
            _make_embedding_response(vector)
        )
        result = ai_service.generate_embedding("test text")
        assert len(result) == 1536
        assert all(isinstance(v, float) for v in result)

    def test_returns_zero_vector_on_error(self, ai_service):
        ai_service._mock_client.embeddings.create.side_effect = RuntimeError("fail")
        result = ai_service.generate_embedding("text")
        assert len(result) == 1536
        assert all(v == 0.0 for v in result)
