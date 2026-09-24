import logging
import os

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from google import genai
from google.genai import types

from chatbot_config import (
    BOT_NAME,
    MAX_HISTORY_MESSAGES,
    MAX_MESSAGE_LENGTH,
    MAX_OUTPUT_TOKENS,
    MODEL_NAME,
    SYSTEM_PROMPT,
)

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise RuntimeError("GEMINI_API_KEY is missing. Add it to your .env file.")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
client = genai.Client(api_key=api_key)

generation_config = types.GenerateContentConfig(
    system_instruction=SYSTEM_PROMPT,
    max_output_tokens=MAX_OUTPUT_TOKENS,
)


def build_contents(history, message):
    contents = []

    if isinstance(history, list):
        for item in history[-MAX_HISTORY_MESSAGES:]:
            if not isinstance(item, dict):
                continue
            role = item.get("role")
            text = str(item.get("text", "")).strip()
            if role in ("user", "model") and text:
                contents.append(
                    types.Content(role=role, parts=[types.Part(text=text)])
                )

    while contents and contents[0].role != "user":
        contents.pop(0)

    contents.append(types.Content(role="user", parts=[types.Part(text=message)]))
    return contents


@app.get("/")
def index():
    return render_template("index.html", bot_name=BOT_NAME)


@app.post("/chat")
def chat():
    payload = request.get_json(silent=True) or {}
    message = str(payload.get("message", "")).strip()

    if not message:
        return jsonify(error="Please type a question."), 400

    if len(message) > MAX_MESSAGE_LENGTH:
        return (
            jsonify(error=f"Keep your question under {MAX_MESSAGE_LENGTH} characters."),
            400,
        )

    contents = build_contents(payload.get("history", []), message)

    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=contents,
            config=generation_config,
        )
    except Exception:
        logger.exception("Gemini request failed")
        return jsonify(error="The service is unavailable right now. Please try again."), 502

    reply = (response.text or "").strip()
    if not reply:
        return jsonify(error="No answer was generated. Please rephrase your question."), 502

    return jsonify(reply=reply)


if __name__ == "__main__":
    app.run(debug=os.getenv("FLASK_DEBUG") == "1")
