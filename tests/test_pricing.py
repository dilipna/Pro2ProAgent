from p2pops.pricing import Usage, estimate_cost_usd, extract_usage


def test_estimate_cost_known_model():
    usage = Usage(input_tokens=1_000_000, output_tokens=1_000_000)
    cost = estimate_cost_usd("groq", "meta-llama/llama-4-scout-17b-16e-instruct", usage)
    assert cost == 0.11 + 0.34


def test_estimate_cost_unknown_model_returns_zero():
    usage = Usage(input_tokens=1000, output_tokens=1000)
    assert estimate_cost_usd("groq", "some-future-model", usage) == 0.0


def test_extract_usage_from_metadata():
    class FakeMessage:
        usage_metadata = {"input_tokens": 120, "output_tokens": 45, "total_tokens": 165}

    usage = extract_usage(FakeMessage())
    assert usage == Usage(input_tokens=120, output_tokens=45)
    assert usage.total_tokens == 165


def test_extract_usage_missing_metadata_returns_none():
    class FakeMessage:
        pass

    assert extract_usage(FakeMessage()) is None


def test_extract_usage_empty_metadata_returns_none():
    class FakeMessage:
        usage_metadata = {}

    assert extract_usage(FakeMessage()) is None
