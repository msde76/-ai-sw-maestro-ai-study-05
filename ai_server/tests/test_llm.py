import pytest

from app.core.config import Settings
from app.core.llm import extract_json_object


def test_settings_defaults_use_upstage_and_pathsdog(monkeypatch):
    monkeypatch.setenv("UPSTAGE_API_KEY", "test-key")
    settings = Settings()

    assert str(settings.upstage_base_url) == "https://api.upstage.ai/v1"
    assert settings.upstage_model == "solar-pro3"
    assert str(settings.pathsdog_mcp_url) == "https://jobs.pathsdog.com/mcp"


def test_extract_json_object_handles_markdown_fence():
    text = '```json\n{"ok": true, "count": 2}\n```'

    assert extract_json_object(text) == {"ok": True, "count": 2}


def test_extract_json_object_rejects_non_object():
    with pytest.raises(ValueError, match="JSON object"):
        extract_json_object("[1, 2, 3]")
