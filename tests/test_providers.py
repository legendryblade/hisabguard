import json

import httpx
import pytest

from app import providers


@pytest.fixture(autouse=True)
def config(monkeypatch):
    for name, value in {
        "LLM_BASE_URL": "https://example.test/v1", "LLM_API_KEY": "test-secret-never-disclose",
        "LLM_MODEL": "test-reasoning", "VISION_MODEL": "test-vision", "STT_BASE_URL": "https://speech.test/v1",
        "STT_API_KEY": "speech-secret", "STT_MODEL": "test-whisper",
        "REASONING_MODE": "default",
    }.items():
        monkeypatch.setenv("HISABGUARD_" + name, value)


def mock_http(monkeypatch, handler):
    real_client = httpx.Client
    monkeypatch.setattr(providers.httpx, "Client", lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs))


def assistant(content=None, tool_calls=None):
    return {"choices": [{"message": {"role": "assistant", "content": content, **({"tool_calls": tool_calls} if tool_calls else {})}}]}


def test_no_other_project_credentials(monkeypatch):
    monkeypatch.delenv("HISABGUARD_LLM_API_KEY")
    monkeypatch.setenv("SHIRI_LLM_API_KEY", "unrelated-secret")
    assert providers.get_status()["model_configured"] is False
    with pytest.raises(providers.ProviderError, match="not configured"):
        providers.agent_turn([], [])


def test_status_never_exposes_key():
    output = json.dumps(providers.get_status())
    assert "secret" not in output
    assert providers.get_status()["vision_configured"]


def test_tool_request_and_real_response_shape(monkeypatch):
    calls = [{"id": "c1", "type": "function", "function": {"name": "get_trip_records", "arguments": '{"trip_id":1}'}}]
    def handler(request):
        assert str(request.url) == "https://example.test/v1/chat/completions"
        assert request.headers["authorization"] == "Bearer test-secret-never-disclose"
        body = json.loads(request.content)
        assert body["tools"][0]["function"]["name"] == "get_trip_records"
        assert body["parallel_tool_calls"] is False
        return httpx.Response(200, json=assistant(tool_calls=calls))
    mock_http(monkeypatch, handler)
    result = providers.agent_turn([{"role": "user", "content": "investigate"}], [{"type": "function", "function": {"name": "get_trip_records"}}])
    assert result["tool_calls"] == calls


def test_vision_transcribes_into_draft_proposal(monkeypatch):
    output = {"kind": "payment", "amount_bdt": "25000.00", "text": "Received BDT 25,000", "confidence": {"amount_bdt": 0.8}}
    def handler(request):
        body = json.loads(request.content)
        assert body["model"] == "test-vision"
        assert body["messages"][1]["content"][1]["image_url"]["url"].startswith("data:image/png;base64,")
        return httpx.Response(200, json=assistant(json.dumps(output)))
    mock_http(monkeypatch, handler)
    assert providers.extract_image(b"fake-test-bytes", "image/png") == output


@pytest.mark.parametrize("content", ["not-json", '{"kind":"payment","amount_bdt":25000}', '{"kind":"payment","amount_bdt":"NaN"}', '{"kind":"payment","kind":"statement"}', '{"kind":"statement","confidence":{"text":4}}'])
def test_bad_vision_output_refuses(monkeypatch, content):
    mock_http(monkeypatch, lambda request: httpx.Response(200, json=assistant(content)))
    with pytest.raises(providers.ProviderError, match="validation"):
        providers.extract_image(b"test", "image/png")


def test_audio_upload_and_bangla_response(monkeypatch):
    def handler(request):
        assert str(request.url).endswith("/audio/transcriptions")
        assert "multipart/form-data" in request.headers["content-type"]
        assert b"test-whisper" in request.content
        assert b"voice.wav" in request.content
        return httpx.Response(200, json={"text": "বাকি টাকা কালকে দেওয়ার কথা।"})
    mock_http(monkeypatch, handler)
    assert "কালকে" in providers.transcribe_audio(b"RIFF-test", "voice.wav", "audio/wav")


@pytest.mark.parametrize("code", [401, 429, 500, 302])
def test_http_errors_do_not_echo_secret(monkeypatch, code):
    mock_http(monkeypatch, lambda request: httpx.Response(code, text="test-secret-never-disclose private statement"))
    with pytest.raises(providers.ProviderError) as exc:
        providers.agent_turn([], [])
    assert str(code) in str(exc.value)
    assert "secret" not in str(exc.value)


def test_timeout_safe(monkeypatch):
    def handler(request):
        raise httpx.ReadTimeout("upstream secret and personal data", request=request)
    mock_http(monkeypatch, handler)
    with pytest.raises(providers.ProviderError, match="timed out") as exc:
        providers.agent_turn([], [])
    assert "secret" not in str(exc.value)


@pytest.mark.parametrize("response", [{}, {"choices": []}, assistant(), {"text": "x"}, []])
def test_missing_assistant_response(monkeypatch, response):
    mock_http(monkeypatch, lambda request: httpx.Response(200, json=response))
    with pytest.raises(providers.ProviderError):
        providers.agent_turn([], [])


def test_credentials_in_endpoint_refused(monkeypatch):
    monkeypatch.setenv("HISABGUARD_LLM_BASE_URL", "https://user:secret@example.test/v1")
    with pytest.raises(providers.ProviderError, match="without credentials"):
        providers.agent_turn([], [])


def test_token_exhaustion_has_specific_safe_error(monkeypatch):
    payload = assistant()
    payload["choices"][0]["finish_reason"] = "length"
    mock_http(monkeypatch, lambda request: httpx.Response(200, json=payload))
    with pytest.raises(providers.ProviderError, match="token budget"):
        providers.agent_turn([], [])


def test_reasoning_extension_only_goes_to_explicit_openrouter(monkeypatch):
    monkeypatch.setenv("HISABGUARD_REASONING_MODE", "off")
    seen = []
    def handler(request):
        seen.append(json.loads(request.content))
        return httpx.Response(200, json=assistant("ok"))
    mock_http(monkeypatch, handler)
    providers.agent_turn([], [])
    assert "reasoning" not in seen[-1]
    monkeypatch.setenv("HISABGUARD_LLM_BASE_URL", "https://openrouter.ai/api/v1")
    providers.agent_turn([], [])
    assert seen[-1]["reasoning"] == {"enabled": False, "exclude": True}


def test_inapplicable_confidence_is_omitted_not_fabricated(monkeypatch):
    output = {"kind": "invoice", "amount_bdt": "32000.00", "delivered": None,
              "confidence": {"amount_bdt": 0.95, "delivered": None}}
    mock_http(monkeypatch, lambda request: httpx.Response(200, json=assistant(json.dumps(output))))
    proposal = providers.extract_image(b"synthetic", "image/png")
    assert proposal["amount_bdt"] == "32000.00"
    assert proposal["confidence"] == {"amount_bdt": 0.95}
