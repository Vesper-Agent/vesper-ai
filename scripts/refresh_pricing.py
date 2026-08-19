"""Refreshes src/vesper/model_costs.json from the LiteLLM pricing list.

Fetches BerriAI/LiteLLM's model_prices_and_context_window.json (MIT licensed),
keeps the chat models for the providers Vesper routes, converts per-token prices
to per-million-token prices, and writes them in Vesper's pricing schema.

Usage:  python scripts/refresh_pricing.py
"""

import os
import json
import urllib.request

SOURCE_URL = "https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json"
PROVIDERS = {"openai", "anthropic", "gemini"}
ROUTABLE = ("gpt-", "o1-", "o3-", "o4-", "claude-", "gemini-")

TARGET_PATH = os.path.join(os.path.dirname(__file__), "..", "src", "vesper", "model_costs.json")

def build_table(raw: dict) -> dict:
    """Filters and transforms the LiteLLM list into Vesper's pricing table."""
    table = {}
    for name, entry in raw.items():
        if not isinstance(entry, dict):
            continue
        if entry.get("litellm_provider") not in PROVIDERS or entry.get("mode") != "chat":
            continue

        input_cost = entry.get("input_cost_per_token")
        output_cost = entry.get("output_cost_per_token")
        if input_cost is None or output_cost is None:
            continue

        model = name.split("/")[-1]
        if not model.startswith(ROUTABLE):
            continue

        table[model] = {
            "input": round(input_cost * 1_000_000, 6),
            "output": round(output_cost * 1_000_000, 6)
        }

    return dict(sorted(table.items()))

def main() -> None:
    raw = json.loads(urllib.request.urlopen(SOURCE_URL, timeout=30).read())
    table = build_table(raw)

    with open(TARGET_PATH, "w") as f:
        json.dump(table, f, indent=2)
        f.write("\n")

    print(f"Wrote {len(table)} models to {os.path.relpath(TARGET_PATH)}")

if __name__ == "__main__":
    main()
