"""NeMo Guardrails wrapper: filters discovered ideas before they reach scoring.

Uses the built-in `self check input` flow with a domain-specific prompt (is
this a legitimate AI-related problem, not spam/unsafe/off-topic) rather than
the generic company-policy example shipped with NeMo Guardrails. The rails'
own LLM call is our provider-agnostic get_chat_model(), via NeMo's
LangChainLLMAdapter, so it honors whichever LLM_PROVIDER is active.
"""

from functools import lru_cache

from nemoguardrails import LLMRails, RailsConfig
from nemoguardrails.integrations.langchain.llm_adapter import LangChainLLMAdapter
from nemoguardrails.rails.llm.options import GenerationOptions

from .chat_model import get_chat_model

_CONFIG_YAML = """
models: []

rails:
  input:
    flows:
      - self check input

prompts:
  - task: self_check_input
    # Reasoning models (gpt-oss, o1/o3, gemini-2.5, deepseek-r1...) spend
    # hidden reasoning tokens before any visible output -- a tight cap tuned
    # for non-reasoning models starves them into an empty response. 300 is
    # still cheap for a yes/no classification but survives that overhead.
    max_tokens: 300
    content: |
      Your task is to check if the input below is a legitimate, specific
      AI-related problem or pain point that a person is facing -- suitable
      for a product team to investigate and potentially build a solution
      for.

      Block the input if it is:
      - spam, an advertisement, or promotional content
      - gibberish or too vague to act on
      - harmful, unsafe, or abusive content
      - not related to AI, software, or developer tooling at all

      Input: "{{ user_input }}"

      Question: Should the input be blocked (Yes or No)? Answer with a
      single word, Yes or No, and nothing else.
      Answer:
"""


@lru_cache
def _get_rails() -> LLMRails:
    config = RailsConfig.from_content(yaml_content=_CONFIG_YAML)
    model = get_chat_model("default")
    return LLMRails(config=config, llm=LangChainLLMAdapter(model))


async def is_idea_allowed(text: str) -> bool:
    """Runs the input guardrail against `text`. True if it passes the filter."""
    rails = _get_rails()
    result = await rails.generate_async(
        messages=[{"role": "user", "content": text}],
        options=GenerationOptions(rails=["input"], output_vars=["allowed"]),
    )
    return bool(result.output_data.get("allowed", True))
