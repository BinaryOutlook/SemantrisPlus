import os

from dotenv import load_dotenv

try:
    from google import genai
except ImportError as exc:  # pragma: no cover - import safety only
    raise RuntimeError(
        "google-genai is not installed. Run `python3 -m pip install -r requirements.txt` first."
    ) from exc


load_dotenv()


def main() -> None:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not found. Add it to your .env file.")

    client = genai.Client(api_key=api_key)
    models = client.models.list()

    for model in models:
        print(model.name)
        print(getattr(model, "display_name", ""))
        print()


if __name__ == "__main__":
    main()
