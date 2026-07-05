from p2pops.config import Settings


def test_defaults_load_without_env_file(monkeypatch, tmp_path):
    # `litellm` calls load_dotenv() on import, which can leak keys from this
    # repo's real .env into os.environ for the rest of the test session --
    # independent of cwd. Strip explicitly so this test isn't order-dependent.
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.chdir(tmp_path)
    settings = Settings(_env_file=None)

    assert settings.environment == "development"
    assert settings.llm_provider == "anthropic"
    assert settings.default_model == "anthropic/claude-haiku-4-5-20251001"
    assert settings.review_interval_days == 10
    assert settings.anthropic_api_key is None
    assert settings.active_api_key is None


def test_openrouter_provider_switches_model_and_key(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    settings = Settings(
        _env_file=None,
        llm_provider="openrouter",
        openrouter_api_key="sk-or-test",
    )

    assert settings.default_model == "openrouter/anthropic/claude-haiku-4.5"
    assert settings.builder_model == "openrouter/anthropic/claude-sonnet-4.5"
    assert settings.active_api_key == "sk-or-test"
