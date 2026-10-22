import logging
import os
from functools import lru_cache

from dotenv import load_dotenv
from groq import Groq

# Reads GROQ_API_KEY from .env locally.
# On HuggingFace Spaces, secrets arrive as environment variables.
load_dotenv()

logger = logging.getLogger(__name__)

# Change the model without touching code: set GROQ_MODEL in .env
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")


@lru_cache(maxsize=1)
def get_client() -> Groq:
    """Create the Groq client on first use, then reuse it."""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY is not set. Add it to your .env file "
            "or to your hosting platform's secrets."
        )
    logger.info(f"Groq client ready, model: {GROQ_MODEL}")
    return Groq(api_key=api_key)