"""Settings shared by the agent team: the one model, the database paths and the loop limits."""

import os
from pathlib import Path

from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic_ai.models.openai import OpenAIResponsesModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.usage import UsageLimits

BACKEND_DIR = Path(__file__).resolve().parent
HW5_DIR = BACKEND_DIR.parent
PROMPTS_DIR = BACKEND_DIR / "prompts"
MCP_SERVER_SCRIPT = HW5_DIR / "mcp_server" / "server.py"

# The working copy is the only database the team touches. The original is the reset point.
DB_PATH = HW5_DIR / "data" / "campus_customs_new.db"
ORIGINAL_DB_PATH = HW5_DIR / "data" / "campus_customs.db"

# The API key lives in .env (HW5/ or the parent AI FOUNDATIONS/ folder), never in code.
load_dotenv(HW5_DIR / ".env")
load_dotenv(HW5_DIR.parent / ".env")

PORTKEY_BASE_URL = "https://api.portkey.ai/v1"

# The ONLY model for every agent. Deliberately not read from the environment, and there is
# no fallback model: if gpt-6-luna is unreachable, the run fails instead of switching models.
MODEL_NAME = "gpt-6-luna"

# ---------- Loop limits ----------
# One ticket = the Boss run plus every delegated run. They share one usage counter, so these
# caps cover the whole ticket, not each agent separately.
TICKET_LIMITS = UsageLimits(request_limit=40, tool_calls_limit=40, total_tokens_limit=300_000)
MAX_DELEGATION_DEPTH = 3   # boss -> agent -> agent -> agent, no deeper
MAX_DELEGATIONS_PER_TICKET = 10
AGENT_RETRIES = 2          # output-validator retries per agent run


def build_model() -> OpenAIResponsesModel:
    api_key = os.getenv("PORTKEY_API_KEY")
    if not api_key:
        raise RuntimeError("PORTKEY_API_KEY is not set. Add it to HW5/.env or the parent folder's .env.")
    client = AsyncOpenAI(
        api_key=api_key,
        base_url=PORTKEY_BASE_URL,
        default_headers={"x-portkey-api-key": api_key},
    )
    return OpenAIResponsesModel(MODEL_NAME, provider=OpenAIProvider(openai_client=client))
