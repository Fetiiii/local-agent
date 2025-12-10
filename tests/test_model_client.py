from backend.core.model_client import ModelClient


def test_model_client_returns_string_on_failure():
    client = ModelClient(base_url="http://127.0.0.1:0")  # invalid port to force fallback
    out = client.generate(messages=[{"role": "user", "content": "hi"}], mode="chat")
    assert isinstance(out, str)


def test_model_client_health_check_false():
    client = ModelClient(base_url="http://127.0.0.1:0")
    assert client.health_check() is False
