import os
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from openai import OpenAI
from pydantic import BaseModel, Field

load_dotenv()

app = FastAPI(title="Veda Travel Planner")
BASE_DIR = Path(__file__).resolve().parent

SYSTEM_MESSAGE = (
    "You are Veda, an expert trip-planning assistant. Help travelers create practical, "
    "well-paced itineraries with thoughtful recommendations for transport, lodging, "
    "food, activities, budgets, accessibility, weather, and local customs. Ask focused "
    "questions when important details are missing. Be transparent when information may "
    "change and never invent live availability, prices, visa rules, or opening hours. "
    "Remind travelers to verify important details with official sources before booking."
)


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=12000)


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(default_factory=list, max_length=50)


class ChatResponse(BaseModel):
    reply: str


def get_client() -> tuple[OpenAI, str]:
    endpoint = os.getenv("AZURE_ENDPOINT", "").strip()
    deployment = os.getenv("AZURE_DEPLOYMENT", "").strip()
    api_key = os.getenv("AZURE_API_KEY", "").strip()
    missing = [
        name
        for name, value in (
            ("AZURE_ENDPOINT", endpoint),
            ("AZURE_DEPLOYMENT", deployment),
            ("AZURE_API_KEY", api_key),
        )
        if not value
    ]
    if missing:
        raise RuntimeError("Missing required Azure configuration")

    base_url = endpoint.rstrip("/")
    if not base_url.endswith("/openai/v1"):
        base_url = f"{base_url}/openai/v1"
    return OpenAI(api_key=api_key, base_url=f"{base_url}/"), deployment


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(BASE_DIR / "index.html", media_type="text/html")


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    if not request.messages:
        raise HTTPException(status_code=400, detail="Send a message to start planning.")
    try:
        client, deployment = get_client()
        response = client.chat.completions.create(
            model=deployment,
            messages=[
                {"role": "system", "content": SYSTEM_MESSAGE},
                *[message.model_dump() for message in request.messages],
            ],
        )
        reply = response.choices[0].message.content
        if not reply:
            raise RuntimeError("The model returned an empty response")
        return ChatResponse(reply=reply)
    except RuntimeError as error:
        raise HTTPException(status_code=500, detail=str(error)) from error
    except Exception as error:
        print(f"Chat request failed: {type(error).__name__}")
        raise HTTPException(status_code=502, detail="The travel assistant is unavailable right now.") from error