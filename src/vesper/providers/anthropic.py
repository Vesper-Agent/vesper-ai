from vesper.providers.base import BaseProvider, LLMResponse, ToolCall
from anthropic import Anthropic

class AnthropicProvider(BaseProvider):
    def __init__(self, model_name: str):
        """Initializes the Anthropic client."""
        super().__init__(model_name)
        self.client = Anthropic()

    def _to_messages(self, messages) -> list:
        """Translates the neutral message history into Anthropic content blocks."""
        result = []
        for message in messages:
            if message["role"] == "tool":
                result.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": message["tool_call_id"],
                        "content": message["content"]
                    }]
                })
            elif message["role"] == "assistant" and message.get("tool_calls"):
                result.append({
                    "role": "assistant",
                    "content": [{
                        "type": "tool_use",
                        "id": call["id"],
                        "name": call["name"],
                        "input": call["arguments"]
                    } for call in message["tool_calls"]]
                })
            else:
                result.append({"role": message["role"], "content": message.get("content", "")})
        return result

    def generate(self, messages, tools=None) -> LLMResponse:
        """Generates the response from the Anthropic client."""
        kwargs = {
            "model": self.model_name,
            "max_tokens": 4096,
            "messages": self._to_messages(messages)
        }
        if tools:
            kwargs["tools"] = [
                {"name": schema["name"], "description": schema["description"], "input_schema": schema["parameters"]}
                for schema in tools
            ]

        response = self.client.messages.create(**kwargs)

        content = ""
        tool_calls = []
        for block in response.content:
            if block.type == "text":
                content += block.text
            elif block.type == "tool_use":
                tool_calls.append(ToolCall(id=block.id, name=block.name, arguments=block.input))

        return LLMResponse(
            content=content,
            prompt_tokens=response.usage.input_tokens,
            completion_tokens=response.usage.output_tokens,
            tool_calls=tool_calls
        )
