import json
import re
from typing import Generator
import openai
from config.settings import (
    DEEPINFRA_API_KEY, DEEPINFRA_BASE_URL,
    LLM_MODEL, EMBED_MODEL, EMBEDDING_BATCH_SIZE,
    LLM_TEMPERATURE, LLM_MAX_TOKENS
)

_openai_client = None


def get_openai_client() -> openai.OpenAI:
    global _openai_client
    if _openai_client is None:
        _openai_client = openai.OpenAI(
            api_key=DEEPINFRA_API_KEY,
            base_url=DEEPINFRA_BASE_URL,
        )
    return _openai_client


def embed_texts(texts: list[str]) -> list[list[float]]:
    client = get_openai_client()
    embeddings = []
    for i in range(0, len(texts), EMBEDDING_BATCH_SIZE):
        batch = texts[i:i + EMBEDDING_BATCH_SIZE]
        response = client.embeddings.create(model=EMBED_MODEL, input=batch)
        embeddings.extend([item.embedding for item in response.data])
    return embeddings


def embed_query(text: str) -> list[float]:
    return embed_texts([text])[0]


def invoke_llm(prompt: str, system: str = None, temperature: float = LLM_TEMPERATURE, max_tokens: int = LLM_MAX_TOKENS) -> str:
    client = get_openai_client()
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    response = client.chat.completions.create(
        model=LLM_MODEL,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content


def stream_llm(prompt: str, system: str = None) -> Generator[str, None, None]:
    client = get_openai_client()
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    stream = client.chat.completions.create(
        model=LLM_MODEL,
        messages=messages,
        temperature=LLM_TEMPERATURE,
        max_tokens=LLM_MAX_TOKENS,
        stream=True,
    )
    for chunk in stream:
        if chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content


def parse_json_response(response: str) -> dict | list | None:
    try:
        return json.loads(response)
    except json.JSONDecodeError:
        json_match = re.search(r'\{[\s\S]*\}|\[[\s\S]*\]', response)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass
    return None


def invoke_llm_json(prompt: str, system: str = None, temperature: float = None, retries: int = 2) -> dict | list | None:
    base_temp = temperature if temperature is not None else LLM_TEMPERATURE
    for attempt in range(retries + 1):
        temp = 0.2 if attempt > 0 else base_temp
        response = invoke_llm(prompt, system=system, temperature=temp)
        parsed = parse_json_response(response)
        if parsed is not None:
            return parsed
    return None
