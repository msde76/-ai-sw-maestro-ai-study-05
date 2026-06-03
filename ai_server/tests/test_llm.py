from pathlib import Path
from types import SimpleNamespace

import pytest

from app.core.config import Settings
from app.core import config as config_module
from app.core.llm import UpstageLLM, extract_json_object


def test_settings_defaults_use_upstage_and_pathsdog(monkeypatch):
    monkeypatch.setenv("UPSTAGE_API_KEY", "test-key")
    settings = Settings()

    assert str(settings.upstage_base_url) == "https://api.upstage.ai/v1"
    assert settings.upstage_model == "solar-pro3"
    assert str(settings.pathsdog_mcp_url) == "https://jobs.pathsdog.com/mcp"


def test_settings_env_file_uses_ai_server_path_when_cwd_is_repo_root(monkeypatch):
    monkeypatch.chdir(Path(__file__).resolve().parents[2])
    monkeypatch.setenv("UPSTAGE_API_KEY", "test-key")

    env_file = Path(Settings.model_config["env_file"])

    assert env_file == Path(config_module.__file__).resolve().parents[2] / ".env"
    assert Settings().upstage_api_key == "test-key"


def test_extract_json_object_handles_markdown_fence():
    text = '```json\n{"ok": true, "count": 2}\n```'

    assert extract_json_object(text) == {"ok": True, "count": 2}


def test_extract_json_object_handles_prose_fence_and_trailing_prose():
    text = """Here is the result:

```json
{"ok": true, "count": 2}
```

Hope that helps.
"""

    assert extract_json_object(text) == {"ok": True, "count": 2}


def test_extract_json_object_handles_embedded_bare_object_in_prose():
    text = 'The answer is {"ok": true, "count": 2} for this request.'

    assert extract_json_object(text) == {"ok": True, "count": 2}


def test_extract_json_object_malformed_json_raises_value_error():
    with pytest.raises(ValueError, match="JSON"):
        extract_json_object('{"ok": true')


def test_extract_json_object_rejects_non_object():
    with pytest.raises(ValueError, match="JSON object"):
        extract_json_object("[1, 2, 3]")


@pytest.mark.asyncio
async def test_complete_json_raises_value_error_for_empty_model_content():
    class FakeCompletions:
        async def create(self, **kwargs):
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=""))])

    llm = UpstageLLM.__new__(UpstageLLM)
    llm._model = "test-model"
    llm._client = SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions()))

    with pytest.raises(ValueError, match="content"):
        await llm.complete_json([{"role": "user", "content": "Return JSON"}])


@pytest.mark.asyncio
async def test_complete_json_passes_json_schema_response_format():
    class FakeCompletions:
        def __init__(self):
            self.kwargs = None

        async def create(self, **kwargs):
            self.kwargs = kwargs
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='{"ok": true}'))])

    completions = FakeCompletions()
    llm = UpstageLLM.__new__(UpstageLLM)
    llm._model = "test-model"
    llm._client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    json_schema = {
        "name": "test_schema",
        "schema": {
            "type": "object",
            "properties": {"ok": {"type": "boolean"}},
            "required": ["ok"],
            "additionalProperties": False,
        },
        "strict": True,
    }

    result = await llm.complete_json([{"role": "user", "content": "Return JSON"}], json_schema=json_schema)

    assert result == {"ok": True}
    assert completions.kwargs["response_format"] == {
        "type": "json_schema",
        "json_schema": json_schema,
    }
