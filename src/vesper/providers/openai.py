import json
from vesper.providers.base import BaseProvider, LLMResponse, ToolCall
from openai import OpenAI

class OpenAIProvider(BaseProvider):
    def __init__(self, model_name: str):
        """Initializes the openai client"""
        super().__init__(model_name)
        self.client = OpenAI()

    def _to_input(self, messages) -> list:
        """Translates the neutral message history into Responses API input items."""
        items = []
        for message in messages:
            if message["role"] == "tool":
                items.append({
                    "type": "function_call_output",
                    "call_id": message["tool_call_id"],
                    "output": message["content"]
                })
            elif message["role"] == "assistant" and message.get("tool_calls"):
                for call in message["tool_calls"]:
                    items.append({
                        "type": "function_call",
                        "call_id": call["id"],
                        "name": call["name"],
                        "arguments": json.dumps(call["arguments"])
                    })
            else:
                items.append({"role": message["role"], "content": message.get("content", "")})
        return items

    def generate(self, messages, tools=None) -> LLMResponse:
        """Generates the response from OpenAI client."""
        kwargs = {"model": self.model_name, "input": self._to_input(messages)}
        if tools:
            kwargs["tools"] = [{"type": "function", **schema} for schema in tools]

        response = self.client.responses.create(**kwargs)

        tool_calls = [
            ToolCall(id=item.call_id, name=item.name, arguments=json.loads(item.arguments))
            for item in response.output if item.type == "function_call"
        ]

        return LLMResponse(
            content=response.output_text,
            prompt_tokens=response.usage.input_tokens,
            completion_tokens=response.usage.output_tokens,
            tool_calls=tool_calls
        )
