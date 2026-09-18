import httpx
import pytest

from app.core.errors import DomainError
from app.db.enums import LlmProvider
from app.services.llm import HttpProviderAdapter


@pytest.mark.parametrize(
    ("status", "code"),
    [
        (401, "llm_authentication_failed"),
        (429, "llm_rate_limited"),
        (503, "llm_provider_unavailable"),
    ],
)
def test_provider_http_errors_are_normalized(
    monkeypatch: pytest.MonkeyPatch, status: int, code: str
) -> None:
    def request(*args: object, **kwargs: object) -> httpx.Response:
        return httpx.Response(status, request=httpx.Request("POST", "https://provider.test"))

    monkeypatch.setattr(httpx, "request", request)
    adapter = HttpProviderAdapter(LlmProvider.OPENAI, "https://provider.test")
    with pytest.raises(DomainError) as error:
        adapter._request("POST", "/v1/chat/completions", "secret")
    assert error.value.code == code
    assert "secret" not in error.value.message


def test_provider_timeout_and_invalid_json_are_normalized(monkeypatch: pytest.MonkeyPatch) -> None:
    def timeout(*args: object, **kwargs: object) -> None:
        raise httpx.ReadTimeout("timeout")

    monkeypatch.setattr(httpx, "request", timeout)
    adapter = HttpProviderAdapter(LlmProvider.OPENAI, "https://provider.test")
    with pytest.raises(DomainError) as timeout_error:
        adapter._request("POST", "/v1/chat/completions", "secret")
    assert timeout_error.value.code == "llm_timeout"

    response = httpx.Response(
        200,
        content=b"not-json",
        request=httpx.Request("POST", "https://provider.test"),
    )
    monkeypatch.setattr(httpx, "request", lambda *args, **kwargs: response)
    with pytest.raises(DomainError) as json_error:
        adapter._request("POST", "/v1/chat/completions", "secret")
    assert json_error.value.code == "llm_invalid_response"
