import os
from agents import OpenAIChatCompletionsModel
from openai import AsyncOpenAI

_openai_client = AsyncOpenAI(
    base_url="https://api.openai.com/v1", api_key=os.getenv("OPENAI_API_KEY")
)
_ollama_client = AsyncOpenAI(base_url="http://localhost:11434/v1", api_key="ollama")

Qwen3 = OpenAIChatCompletionsModel(model="qwen3", openai_client=_ollama_client)
Gemma3 = OpenAIChatCompletionsModel(model="gemma3", openai_client=_openai_client)
Gpt4o = OpenAIChatCompletionsModel(model="gpt-4o", openai_client=_openai_client)
Gpt4oMini = OpenAIChatCompletionsModel(
    model="gpt-4o-mini", openai_client=_openai_client
)

AGENT_MODEL = Qwen3
MULTIMODAL_MODEL = Gemma3
