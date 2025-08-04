import os
from agents import OpenAIChatCompletionsModel
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv(override=True)

_openai_client = AsyncOpenAI(
    base_url="https://api.openai.com/v1", api_key=os.getenv("OPENAI_API_KEY")
)
_ollama_client = AsyncOpenAI(base_url="http://localhost:11434/v1", api_key="ollama")
_open_router = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1", api_key=os.getenv("OPENROUTER_API_KEY")
)

Qwen3 = OpenAIChatCompletionsModel(model="qwen3", openai_client=_ollama_client)
Gemma3 = OpenAIChatCompletionsModel(model="gemma3", openai_client=_openai_client)
Gpt4o = OpenAIChatCompletionsModel(model="gpt-4o", openai_client=_openai_client)
Gpt4oMini = OpenAIChatCompletionsModel(
    model="gpt-4o-mini", openai_client=_openai_client
)

Qwen3_480B_Coder = OpenAIChatCompletionsModel(
    model="qwen/qwen3-coder:free", openai_client=_open_router
)
Qwen3_235B_A22B = OpenAIChatCompletionsModel(
    model="qwen/qwen3-235b-a22b:free", openai_client=_open_router
)
Qwen2_5_72B_Instruct = OpenAIChatCompletionsModel(
    model="qwen/qwen-2.5-72b-instruct:free", openai_client=_open_router
)
Deepseek_R1_0528 = OpenAIChatCompletionsModel(
    model="deepseek/deepseek-r1-0528:free", openai_client=_open_router
)
Deepseek_Chat_V3_0324 = OpenAIChatCompletionsModel(
    model="deepseek/deepseek-chat-v3-0324:free", openai_client=_open_router
)

AGENT_MODEL = Qwen3_480B_Coder
MULTIMODAL_MODEL = Gpt4oMini
