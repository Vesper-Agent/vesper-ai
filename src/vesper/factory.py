import os
import json
from typing import Optional

from vesper.exceptions import ModelNotSupportedError
from vesper.providers.base import BaseProvider
from vesper.providers.openai import OpenAIProvider
from vesper.providers.anthropic import AnthropicProvider
from vesper.providers.google import GoogleProvider

_COSTS_PATH = os.path.join(os.path.dirname(__file__), "model_costs.json")

with open(_COSTS_PATH) as f:
    MODEL_COSTS = json.load(f)

def calculate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> Optional[float]:
    """Calculates the dollar cost from token counts, or None if the model has no pricing."""
    if model not in MODEL_COSTS:
        return None

    input_price = MODEL_COSTS[model]["input"]
    output_price = MODEL_COSTS[model]["output"]

    return ((prompt_tokens * input_price) + (completion_tokens * output_price)) / 1_000_000

def get_provider(model_name: str) -> BaseProvider:
    """Instantiates and returns the correct provider based on model name."""
    if model_name.startswith(("gpt-", "o1-", "o3-")):
        return OpenAIProvider(model_name)
    elif model_name.startswith("claude-"):
        return AnthropicProvider(model_name)
    elif model_name.startswith("gemini-"):
        return GoogleProvider(model_name)
    else:
        raise ModelNotSupportedError(f"Model '{model_name}' is currently not supported by Vesper.")