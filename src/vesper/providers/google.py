from vesper.providers.base import BaseProvider, LLMResponse, ToolCall
from google import genai

class GoogleProvider(BaseProvider):
    def __init__(self, model_name: str):
        """Initializes the Gemini client."""
        super().__init__(model_name)
        self.client = genai.Client()

    def _to_contents(self, messages) -> list:
        """Translates the neutral message history into Gemini content parts."""
        contents = []
        for message in messages:
            if message["role"] == "tool":
                contents.append({
                    "role": "user",
                    "parts": [{"function_response": {"name": message["name"], "response": {"result": message["content"]}}}]
                })
            elif message["role"] == "assistant" and message.get("tool_calls"):
                parts = []
                for call in message["tool_calls"]:
                    part = {"function_call": {"name": call["name"], "args": call["arguments"]}}
                    if call.get("signature") is not None:
                        part["thought_signature"] = call["signature"]
                    parts.append(part)
                contents.append({"role": "model", "parts": parts})
            else:
                role = "model" if message["role"] == "assistant" else message["role"]
                contents.append({"role": role, "parts": [{"text": message.get("content", "")}]})
        return contents

    def generate(self, messages, tools=None) -> LLMResponse:
        """Generates the response from the Gemini client."""
        config = None
        if tools:
            config = {"tools": [{"function_declarations": tools}]}

        response = self.client.models.generate_content(
            model=self.model_name,
            contents=self._to_contents(messages),
            config=config
        )

        parts = response.candidates[0].content.parts
        content = "".join(part.text for part in parts if part.text)
        tool_calls = [
            ToolCall(
                id=part.function_call.name,
                name=part.function_call.name,
                arguments=dict(part.function_call.args or {}),
                signature=getattr(part, "thought_signature", None)
            )
            for part in parts if part.function_call
        ]

        return LLMResponse(
            content=content,
            prompt_tokens=response.usage_metadata.prompt_token_count,
            completion_tokens=response.usage_metadata.candidates_token_count,
            tool_calls=tool_calls
        )
