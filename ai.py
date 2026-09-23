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
    "extract": "gemini-3.5-flash-lite",
    "flashcard": "gemini-3.5-flash-lite",
    "teach": "gemini-3.8-flash",
    "question": "gemini-3.8-flash",
    "validate": "gemini-3.8-flash",
    "evaluate": "gemini-3.8-flash",
    "default": "gemini-3.8-flash",
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
    if not r.ok:
        raise RuntimeError(f"Gemini API error {r.status_code}: {r.text[:1000]}")
    data = r.json()
    candidates = data.get("candidates") or []
    if not candidates:
        raise RuntimeError(f"Gemini returned no candidates: {json.dumps(data)[:1000]}")
    parts = candidates[0].get("content", {}).get("parts", [])
    text = next((p.get("text") for p in parts if p.get("text")), None)
    if not text:
        raise RuntimeError(f"Gemini returned no text: {json.dumps(data)[:1000]}")
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Gemini returned invalid JSON: {text[:1000]}") from exc


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


# JSON Schemas used by Gemini/OpenAI structured output.
_SCHEMA = {
    "extract": {"type": "object", "properties": {
        "concepts": {"type": "array", "items": {"type": "object", "properties": {
            "label": {"type": "string"}, "kind": {"type": "string"},
            "content": {"type": "string"}, "source_ref": {"type": "string"}
        }, "required": ["label", "kind", "content", "source_ref"], "additionalProperties": False}}
    }, "required": ["concepts"], "additionalProperties": False},
    "teach": {"type": "object", "properties": {
        "notes": {"type": "array", "items": {"type": "string"}},
        "question_map": {"type": "array", "items": {"type": "object", "properties": {
            "difficulty": {"type": "string", "enum": ["easy", "moderate", "advanced"]},
            "pattern": {"type": "string"}, "recognition": {"type": "string"}, "trap": {"type": "string"}
        }, "required": ["difficulty", "pattern", "recognition", "trap"], "additionalProperties": False}},
        "traps": {"type": "array", "items": {"type": "string"}},
        "external_additions": {"type": "array", "items": {"type": "string"}}
    }, "required": ["notes", "question_map", "traps", "external_additions"], "additionalProperties": False},
    "flashcard": {"type": "object", "properties": {
        "cards": {"type": "array", "items": {"type": "object", "properties": {
            "front": {"type": "string"}, "back": {"type": "string"},
            "source_ref": {"type": "string"}, "concept_label": {"type": "string"}
        }, "required": ["front", "back", "source_ref", "concept_label"], "additionalProperties": False}}
    }, "required": ["cards"], "additionalProperties": False},
    "question": {"type": "object", "properties": {
        "questions": {"type": "array", "items": {"type": "object", "properties": {
            "difficulty": {"type": "string", "enum": ["easy", "moderate", "advanced"]},
            "qtype": {"type": "string"}, "prompt": {"type": "string"},
            "options": {"type": "array", "items": {"type": "string"}},
            "answer": {"type": "string"}, "explanation": {"type": "string"}, "source_ref": {"type": "string"}
        }, "required": ["difficulty", "qtype", "prompt", "options", "answer", "explanation", "source_ref"], "additionalProperties": False}}
    }, "required": ["questions"], "additionalProperties": False},
    "validate": {"type": "object", "properties": {
        "valid": {"type": "boolean"},
        "issues": {"type": "array", "items": {"type": "object", "properties": {
            "type": {"type": "string"}, "item": {"type": "string"},
            "severity": {"type": "string", "enum": ["high", "medium", "low"]}, "fix": {"type": "string"}
        }, "required": ["type", "item", "severity", "fix"], "additionalProperties": False}}
    }, "required": ["valid", "issues"], "additionalProperties": False},
    "evaluate": {"type": "object", "properties": {
        "items": {"type": "array", "items": {"type": "object", "properties": {
            "question_id": {"type": "integer"}, "correct": {"type": "boolean"},
            "error_type": {"type": "string"}, "error_detail": {"type": "string"}, "repair_skill": {"type": "string"}
        }, "required": ["question_id", "correct", "error_type", "error_detail", "repair_skill"], "additionalProperties": False}},
        "weaknesses": {"type": "array", "items": {"type": "object", "properties": {
            "label": {"type": "string"}, "severity": {"type": "integer"}, "reason": {"type": "string"}
        }, "required": ["label", "severity", "reason"], "additionalProperties": False}},
        "repair_actions": {"type": "array", "items": {"type": "object", "properties": {
            "action": {"type": "string"}, "priority": {"type": "string", "enum": ["high", "medium", "low"]}
        }, "required": ["action", "priority"], "additionalProperties": False}}
    }, "required": ["items", "weaknesses", "repair_actions"], "additionalProperties": False}
}


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
        schema_name="extract",
        schema=_SCHEMA["extract"],
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
        schema_name="teach",
        schema=_SCHEMA["teach"],
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
        schema_name="flashcard",
        schema=_SCHEMA["flashcard"],
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
        schema_name="question",
        schema=_SCHEMA["question"],
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
        schema_name="validate",
        schema=_SCHEMA["validate"],
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
        schema_name="evaluate",
        schema=_SCHEMA["evaluate"],
    )
