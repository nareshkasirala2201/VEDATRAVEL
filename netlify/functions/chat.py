import json
import os

from openai import OpenAI


SYSTEM_MESSAGE = (
    "You are Veda, an expert trip-planning assistant. Help travelers create practical, "
    "well-paced itineraries with thoughtful recommendations for transport, lodging, "
    "food, activities, budgets, accessibility, weather, and local customs. Ask focused "
    "questions when important details are missing. Be transparent when information may "
    "change and never invent live availability, prices, visa rules, or opening hours. "
    "Remind travelers to verify important details with official sources before booking."
)


def response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json; charset=utf-8"},
        "body": json.dumps(body),
    }


def handler(event, context):
    if event.get("httpMethod") != "POST":
        return response(405, {"error": "Method not allowed"})

    try:
        payload = json.loads(event.get("body") or "{}")
        messages = payload.get("messages")
        if not isinstance(messages, list) or not messages:
            return response(400, {"error": "Send a message to start planning."})

        endpoint = (os.getenv("AZURE_ENDPOINT") or os.getenv("PROJECT_ENDPOINT") or "").strip()
        deployment = (os.getenv("AZURE_DEPLOYMENT") or "").strip()
        api_key = (os.getenv("AZURE_API_KEY") or os.getenv("PROJECT_APIKEY") or "").strip()
        if not endpoint or not deployment or not api_key:
            return response(500, {"error": "The travel assistant is not configured."})

        base_url = endpoint.rstrip("/")
        if not base_url.endswith("/openai/v1"):
            base_url = f"{base_url}/openai/v1"
        client = OpenAI(api_key=api_key, base_url=f"{base_url}/")
        safe_messages = [
            {"role": item.get("role"), "content": item.get("content")}
            for item in messages
            if item.get("role") in {"user", "assistant"} and isinstance(item.get("content"), str)
        ]
        if not safe_messages:
            return response(400, {"error": "No valid messages were provided."})
        completion = client.chat.completions.create(
            model=deployment,
            messages=[{"role": "system", "content": SYSTEM_MESSAGE}, *safe_messages],
        )
        reply = completion.choices[0].message.content
        if not reply:
            return response(502, {"error": "The assistant returned an empty reply."})
        return response(200, {"reply": reply})
    except (json.JSONDecodeError, TypeError):
        return response(400, {"error": "Invalid JSON request."})
    except Exception as error:
        print(f"Chat request failed: {type(error).__name__}")
        return response(502, {"error": "The travel assistant is unavailable right now."})