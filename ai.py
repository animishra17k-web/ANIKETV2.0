import json
import os

import requests
from dotenv import load_dotenv

load_dotenv()

BASE = """You are a layer inside a persistent SSC CGL preparation OS.
The student is not a beginner. Use supplied source material as primary authority.
Never invent facts. Do not silently add outside content.
If external clarification is necessary, explicitly label it.
Separate source knowledge from learner-performance data.
Return ONLY the requested JSON object."""

# Task -> preferred Gemini model (free-tier first)
# Lightweight tasks use Flash-Lite; reasoning tasks use Flash.
_GEMINI_TASK_MODELS = {
    "extract": "gemini-2.5-flash-lite",
    "flashcard": "gemini-2.5-flash-lite",
    "teach": "gemini-2.5-flash",
    "question": "gemini-2.5-flash",
    "validate": "gemini-2.5-flash",
    "evaluate": "gemini-2.5-flash",
    "default": "gemini-2.5-flash",
}


def _gemini_model_for(task):
    """Return the least-powerful free-capable model for the task."""
    override = os.getenv("GEMINI_MODEL", "").strip()
    if override:
        return override
    if task:
        return _GEMINI_TASK_MODELS.get(str(task).lower(), _GEMINI_TASK_MODELS["default"])
    return _GEMINI_TASK_MODELS["default"]


def _call_ollama(prompt):
    model = os.getenv("OLLAMA_MODEL", "").strip()
    if not model:
        raise RuntimeError("OLLAMA_MODEL is not configured")
    r = requests.post(
        os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/") + "/api/chat",
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": BASE},
                {"role": "user", "content": prompt},
            ],
            "stream": False,
            "format": "json",
        },
        timeout=600,
    )
    r.raise_for_status()
    return json.loads(r.json()["message"]["content"])


def _call_openai(prompt, schema_name=None, schema=None):
    from openai import OpenAI

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    model = os.getenv("OPENAI_MODEL", "").strip()
    if not api_key or not model:
        raise RuntimeError("OPENAI_API_KEY and OPENAI_MODEL are required when AI_PROVIDER=openai")

    client = OpenAI(api_key=api_key)
    kwargs = {
        "model": model,
        "instructions": BASE,
        "input": prompt,
    }
    if schema:
        kwargs["text"] = {
            "format": {
                "type": "json_schema",
                "name": schema_name or "response",
                "strict": True,
                "schema": schema,
            }
        }
    resp = client.responses.create(**kwargs)
    return json.loads(resp.output_text)


def _call_gemini(prompt, task=None, schema=None):
    """
    Free-tier Gemini via REST (no paid OpenAI required).
    Uses pure requests so no extra dependency is required.
    """
    api_key = os.getenv("GEMINI_API_KEY", "").strip() or os.getenv("GOOGLE_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY (or GOOGLE_API_KEY) is required when AI_PROVIDER=gemini")

    model = _gemini_model_for(task)
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

    body = {
        "systemInstruction": {"parts": [{"text": BASE}],},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.2,
        },
    }
    if schema:
        body["generationConfig"]["responseSchema"] = schema

    r = requests.post(
        url,
        params={"key": api_key},
        headers={"Content-Type": "application/json"},
        json=body,
        timeout=600,
    )
    r.raise_for_status()
    data = r.json()
    text = data["candidates"][0]["content"]["parts"][0]["text"]
    return json.loads(text)


def ask(prompt, schema_name=None, schema=None, task=None):
    """
    Provider-agnostic entry point.
    AI_PROVIDER = ollama | gemini | openai  (default: ollama)
    Gemini is free-first and does not require OpenAI.
    """
    provider = os.getenv("AI_PROVIDER", "ollama").lower()

    if provider == "ollama":
        return _call_ollama(prompt)
    if provider == "gemini":
        return _call_gemini(prompt, task=task, schema=schema)
    if provider == "openai":
        return _call_openai(prompt, schema_name=schema_name, schema=schema)

    raise RuntimeError(
        f"Unsupported AI_PROVIDER: {provider}. Use ollama, gemini, or openai."
    )


def build_extract(source, subject, topic):
    return ask(
        f"""LAYER: EXTRACT
SUBJECT: {subject}
TOPIC: {topic}
SOURCE:
{source}

Extract atomic, testable knowledge.
Return:
{{"concepts":[{{"label":"","kind":"rule|formula|fact|definition|exception|method|distinction",
"content":"","source_ref":""}}]}}""",
        task="extract",
    )


def build_teach(concepts, subject, topic):
    return ask(
        f"""LAYER: TEACH
SUBJECT: {subject}
TOPIC: {topic}
ATOMIC KNOWLEDGE:
{json.dumps(concepts, ensure_ascii=False)}

Return:
{{"notes":[], "question_map":[{{"difficulty":"easy|moderate|advanced",
"pattern":"","recognition":"","trap":""}}], "traps":[], "external_additions":[]}}""",
        task="teach",
    )


def build_cards(concepts, notes, topic):
    return ask(
        f"""LAYER: FLASHCARD
TOPIC: {topic}
CONCEPTS:
{json.dumps(concepts, ensure_ascii=False)}
NOTES:
{json.dumps(notes, ensure_ascii=False)}

Create 30-100 high-value recall cards. One focused fact/rule per card.
Return {{"cards":[{{"front":"","back":"","source_ref":"","concept_label":""}}]}}""",
        task="flashcard",
    )


def build_questions(concepts, qmap, topic, n):
    return ask(
        f"""LAYER: QUESTION
TOPIC: {topic}
KNOWLEDGE:
{json.dumps(concepts, ensure_ascii=False)}
QUESTION MAP:
{json.dumps(qmap, ensure_ascii=False)}

Create exactly {n} SSC-style questions when source supports it.
Mix supported difficulty and question types. Do not fabricate unsupported facts.
For objective questions, make answer match either a full option string or its A/B/C/D label.
Return:
{{"questions":[{{"difficulty":"easy|moderate|advanced","qtype":"",
"prompt":"","options":[],"answer":"","explanation":"","source_ref":""}}]}}""",
        task="question",
    )


def validate(pack):
    return ask(
        f"""LAYER: VALIDATE
Review the following generated study pack:
{json.dumps(pack, ensure_ascii=False)}

Find unsupported claims, ambiguous questions, wrong answers, duplicates,
overly trivial cards, and source-traceability problems.
Return:
{{"valid":true,"issues":[{{"type":"","item":"","severity":"high|medium|low","fix":""}}]}}""",
        task="validate",
    )


def evaluate(topic, questions, answers, deterministic=None):
    deterministic = deterministic or []
    return ask(
        f"""LAYER: EVALUATE
TOPIC: {topic}

QUESTIONS AND USER ANSWERS:
{json.dumps(list(zip(questions, answers)), ensure_ascii=False)}

DETERMINISTIC CORRECTNESS (AUTHORITATIVE):
{json.dumps(deterministic, ensure_ascii=False)}

Do not change the correct/incorrect status. Analyze only the learner's errors.
Classify each incorrect answer with the most useful error_type and explain the repair.
Return:
{{"items":[{{"question_id":0,"correct":false,"error_type":"",
"error_detail":"","repair_skill":""}}],
"weaknesses":[{{"label":"","severity":1,"reason":""}}],
"repair_actions":[{{"action":"","priority":"high|medium|low"}}]}}
Error types: concept_gap, recall_gap, formula_rule_gap, application_error,
misread_question, calculation_error, careless_error, vocabulary_gap,
fact_gap, time_pressure, guessing, other.""",
        task="evaluate",
    )
