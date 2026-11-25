
import os
from pathlib import Path

import litellm
from dotenv import load_dotenv

# --------------------------------------------------
# 1. Load environment variables
# --------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

API_KEYS = [
    key.strip()
    for key in os.getenv("LLM_API_KEYS", "").split(",")
    if key.strip()
]

MODELS = [
    model.strip()
    for model in os.getenv("LLM_MODELS", "").split(",")
    if model.strip()
]

if not API_KEYS:
    raise RuntimeError("No API keys configured in .env")

if len(API_KEYS) != len(MODELS):
    raise RuntimeError(
        "LLM_API_KEYS and LLM_MODELS must contain the same number of entries"
    )

# --------------------------------------------------
# 2. Enable LiteLLM built-in caching
# --------------------------------------------------

litellm.enable_cache(type="local")


# --------------------------------------------------
# 3. Custom exception
# --------------------------------------------------

class ProvidersUnavailableError(Exception):
    def __init__(self, attempts):
        self.attempts = attempts
        super().__init__("All providers unavailable")


# --------------------------------------------------
# 4. Parse simulated failures
# --------------------------------------------------

def parse_simulated_failures(header_value: str):
    """
    Supported examples:
        key_1=429
        key_1=500,key_2=500
        *=429
    """

    failures = {}

    if not header_value:
        return failures

    for item in header_value.split(","):
        if "=" not in item:
            continue

        key_id, status = item.strip().split("=", 1)

        try:
            status_code = int(status.strip())

            if status_code in (429, 500, 502, 503, 504):
                failures[key_id.strip()] = status_code

        except ValueError:
            continue

    return failures


# --------------------------------------------------
# 5. Generate response with automatic failover
# --------------------------------------------------

async def generate_response(messages, failure_header=""):

    failures = parse_simulated_failures(failure_header)

    fallback_attempts = 0

    for index, (api_key, model) in enumerate(
        zip(API_KEYS, MODELS)
    ):

        key_id = f"key_{index + 1}"

        try:

            # Check whether this provider should simulate a failure
            simulated_status = failures.get(
                key_id,
                failures.get("*")
            )

            if simulated_status:
                raise RuntimeError(
                    f"Simulated HTTP {simulated_status} for {key_id}"
                )

            # Call the configured LLM provider
            response = await litellm.acompletion(
                model=model,
                messages=messages,
                api_key=api_key,
                caching=True,
                temperature=0.7,
            )

            # Extract generated response
            answer = response.choices[0].message.content or ""

            # Extract token usage
            usage = response.usage

            input_tokens = (
                usage.prompt_tokens if usage else 0
            )

            output_tokens = (
                usage.completion_tokens if usage else 0
            )

            # Detect LiteLLM cache hit
            hidden_params = getattr(
                response,
                "_hidden_params",
                {}
            ) or {}

            cache_hit = hidden_params.get("cache_hit", False)

            response_source = (
                "LLM_CACHE" if cache_hit else "LIVE_INFERENCE"
            )

            return {
                "response": answer,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "model": model,
                "key_id": key_id,
                "fallback_attempts": fallback_attempts,
                "response_source": response_source,
            }

        except Exception as error:

            # Hide API keys from terminal logs
            error_message = str(error).replace(
                api_key,
                "[REDACTED]"
            )

            print(
                f"Provider {key_id} failed: "
                f"{type(error).__name__}: "
                f"{error_message[:500]}"
            )

            fallback_attempts += 1

            # Continue to the next provider
            continue

    # All configured providers failed
    raise ProvidersUnavailableError(
        attempts=fallback_attempts
    )
