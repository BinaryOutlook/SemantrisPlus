import os
import time
import requests
import statistics
from dotenv import load_dotenv

# Load .env variables
load_dotenv()

# Import Gemini + OpenAI clients
try:
    from google import genai
except Exception:  # pragma: no cover - import safety only
    genai = None

from openai import OpenAI


# ============================================================
#                CONFIGURATION
# ============================================================

API_PROVIDER = "OPENAI"     # "OPENAI" / "GEMINI" / "MOCK"

NUM_REQUESTS = 10
CLUE = "Watercraft"
WORDS = ["Harbor", "Signal", "Forest", "Circuit", "Embassy",
         "Runway", "Gallery", "Cipher", "Orbit", "Station",
         "Contract", "Anchor"]

MOCK_URL = "https://httpbin.org/post"

PROMPT_TEMPLATE = """
Rank all words in the list by their semantic association to the clue.
Return ONLY the single best (most related) word.

Clue: {clue}
Words: {words}
"""


# ============================================================
#             LLM CLIENT ABSTRACTIONS
# ============================================================

class LLMClientBase:
    """Base interface for all providers."""
    def generate(self, prompt: str) -> str:
        raise NotImplementedError


# -------------------- MOCK PROVIDER -------------------------

class MockClient(LLMClientBase):
    def generate(self, prompt: str) -> str:
        """
        We do NOT call LLM here, instead we only call httpbin to measure pure network latency.
        """
        response = requests.post(MOCK_URL, json={"prompt": prompt}, timeout=15)
        response.raise_for_status()
        return "mock-result"


# -------------------- GEMINI PROVIDER ------------------------

class GeminiClient(LLMClientBase):
    def __init__(self, model="gemini-2.5-flash-lite"):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY not set in environment")
        if genai is None:
            raise RuntimeError("google-genai is not installed")

        self.client = genai.Client(api_key=api_key)
        self.model = model
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


# -------------------- OPENAI (SILICONFLOW) PROVIDER ------------------------

class OpenAIClient(LLMClientBase):
    def __init__(self, model="Pro/deepseek-ai/DeepSeek-V3.2-Exp"):
    # def __init__(self, model="Qwen/Qwen3-VL-32B-Instruct"):

        
        # 1. Load the key into a variable
        api_key = os.getenv("SiliconFlow_API_KEY")
        if not api_key:
            raise ValueError("SiliconFlow_API_KEY not set in environment")

        # IMPORTANT: set SiliconFlow base URL
        self.client = OpenAI(
            api_key=api_key,  # <--- FIX 1: Use the 'api_key' variable defined above
            base_url="https://api.siliconflow.cn/v1" # <--- CHANGED from .com to .cn
        )

        self.model = model

    def generate(self, prompt: str) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=20,
            temperature=0.0
        )

        # Extract answer text
        # <--- FIX 2: Access content as an attribute (.content) not a dict key (["content"])
        return response.choices[0].message.content.strip()

# ============================================================
#               LATENCY TESTING ENGINE
# ============================================================

def test_latency(llm: LLMClientBase, num=NUM_REQUESTS):
    latencies = []

    print("\n--- Starting Latency Test ---")
    print(f"API Provider: {API_PROVIDER}")
    print(f"Requests: {num}\n")

    prompt = PROMPT_TEMPLATE.format(clue=CLUE, words=str(WORDS)) # Ensure words are stringified for prompt

    for i in range(num):
        print(f"Sending request {i+1}/{num}...", end="", flush=True)

        start = time.perf_counter()
        try:
            result = llm.generate(prompt)
            end = time.perf_counter()
            duration_ms = (end - start) * 1000

            latencies.append(duration_ms)
            print(f" Success: {duration_ms:.2f} ms  (Top word: {result})")

        except Exception as e:
            print(f" FAILED: {e}")

        time.sleep(0.5)

    return latencies


def print_stats(latencies):
    if not latencies:
        print("\nNo successful requests.")
        return

    print("\n--- Latency Statistics ---")
    print(f"Average: {statistics.mean(latencies):.2f} ms")
    print(f"Median:  {statistics.median(latencies):.2f} ms")
    print(f"Min:     {min(latencies):.2f} ms")
    print(f"Max:     {max(latencies):.2f} ms")


# ============================================================
#                      MAIN LOGIC
# ============================================================

if __name__ == "__main__":

    # Select provider
    if API_PROVIDER == "MOCK":
        client = MockClient()

    elif API_PROVIDER == "GEMINI":
        client = GeminiClient()

    elif API_PROVIDER == "OPENAI":
        client = OpenAIClient()

    else:
        raise ValueError(f"Unknown API_PROVIDER: {API_PROVIDER}")

    # Run latency test
    lat = test_latency(client)
    print_stats(lat)
