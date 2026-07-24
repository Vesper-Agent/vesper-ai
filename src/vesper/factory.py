from vesper.exceptions import ModelNotSupportedError
from vesper.providers.base import BaseProvider
from vesper.providers.openai import OpenAIProvider

MODEL_COSTS = {
    "gpt-4o": {
        "input": 2.50,
        "output": 10.00
    },
    "gpt-4o-mini": {
        "input": 0.15,
        "output": 0.60
    },
    "claude-3-5-sonnet-20240620": {
        "input": 3.00,
        "output": 15.00
    },
    "gemini-1.5-pro": {
        "input": 3.50,
        "output": 10.50 
    }
}

def calculate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Calculates the dollar cost from input and output token counts."""
    if model not in MODEL_COSTS:
        raise ModelNotSupportedError(f"Model '{model}' is currently not supported by Vesper.")
    
    input_price = MODEL_COSTS[model]["input"]
    output_price = MODEL_COSTS[model]["output"]
    
    return ((prompt_tokens * input_price) + (completion_tokens * output_price)) / 1_000_000

def get_provider(model_name: str) -> BaseProvider:
    """Instantiates and returns the correct provider based on model name."""
    if model_name.startswith(("gpt-", "o1-", "o3-")):
        return OpenAIProvider(model_name)
    else:
        raise ModelNotSupportedError(f"Model '{model_name}' is currently not supported by Vesper.")