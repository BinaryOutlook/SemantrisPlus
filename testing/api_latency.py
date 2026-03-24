import os
import statistics
import time

import requests
from dotenv import load_dotenv

load_dotenv()

try:
    from google import genai
except Exception:  # pragma: no cover - import safety only
    genai = None

try:
    from openai import OpenAI
except Exception:  # pragma: no cover - import safety only
    OpenAI = None


API_PROVIDER = os.getenv("SEMANTRIS_LLM_PROVIDER", "gemini").strip().lower()

NUM_REQUESTS = 10
CLUE = "Watercraft"
WORDS = [
    "Harbor",
    "Signal",
    "Forest",
    "Circuit",
    "Embassy",
    "Runway",
    "Gallery",
    "Cipher",
    "Orbit",
    "Station",
    "Contract",
    "Anchor",
]

MOCK_URL = "https://httpbin.org/post"

PROMPT_TEMPLATE = """
Rank all words in the list by their semantic association to the clue.
Return ONLY the single best (most related) word.

Clue: {clue}
Words: {words}
""".strip()


class LLMClientBase:
    def generate(self, prompt: str) -> str:
        raise NotImplementedError


class MockClient(LLMClientBase):
    def generate(self, prompt: str) -> str:
        response = requests.post(MOCK_URL, json={"prompt": prompt}, timeout=15)
        response.raise_for_status()
        return "mock-result"


class GeminiClient(LLMClientBase):
    def __init__(self, model: str | None = None):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY not set in environment")
        if genai is None:
            raise RuntimeError("google-genai is not installed")

        self.client = genai.Client(api_key=api_key)
        self.model = model or os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")
        self.config = {
            "temperature": 0.0,
            "max_output_tokens": 20,
        }

    def generate(self, prompt: str) -> str:
        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=self.config,
        )
        return response.text.strip()


class OpenAIClient(LLMClientBase):
    def __init__(self, model: str | None = None, base_url: str | None = None):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not set in environment")
        if OpenAI is None:
            raise RuntimeError("openai is not installed")

        resolved_base_url = base_url or os.getenv("OPENAI_BASE_URL")
        if not resolved_base_url:
            raise ValueError("OPENAI_BASE_URL not set in environment")

        self.client = OpenAI(
            api_key=api_key,
            base_url=resolved_base_url,
        )
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-5.2-mini")

    def generate(self, prompt: str) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=20,
            temperature=0.0,
        )
        return response.choices[0].message.content.strip()


def test_latency(llm: LLMClientBase, num: int = NUM_REQUESTS):
    latencies = []

    print("\n--- Starting Latency Test ---")
    print(f"API Provider: {API_PROVIDER}")
    print(f"Requests: {num}\n")

    prompt = PROMPT_TEMPLATE.format(clue=CLUE, words=str(WORDS))

    for index in range(num):
        print(f"Sending request {index + 1}/{num}...", end="", flush=True)

        start = time.perf_counter()
        try:
            result = llm.generate(prompt)
            end = time.perf_counter()
            duration_ms = (end - start) * 1000

            latencies.append(duration_ms)
            print(f" Success: {duration_ms:.2f} ms  (Top word: {result})")
        except Exception as exc:
            print(f" FAILED: {exc}")

        time.sleep(0.5)

    return latencies


def print_stats(latencies) -> None:
    if not latencies:
        print("\nNo successful requests.")
        return

    print("\n--- Latency Statistics ---")
    print(f"Average: {statistics.mean(latencies):.2f} ms")
    print(f"Median:  {statistics.median(latencies):.2f} ms")
    print(f"Min:     {min(latencies):.2f} ms")
    print(f"Max:     {max(latencies):.2f} ms")


if __name__ == "__main__":
    if API_PROVIDER == "mock":
        client = MockClient()
    elif API_PROVIDER == "gemini":
        client = GeminiClient()
    elif API_PROVIDER == "openai":
        client = OpenAIClient()
    else:
        raise ValueError("Unknown SEMANTRIS_LLM_PROVIDER. Expected 'gemini', 'openai', or 'mock'.")

    latencies = test_latency(client)
    print_stats(latencies)
