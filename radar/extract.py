"""Reading .env and talking to the OpenAI-compatible endpoint with urllib.

Only the standard library. The key never appears in code, in the repository or in
any file this program writes: it is read from the environment, or from a local
`.env` that `.gitignore` excludes.
"""

import json
import os
import re
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_FILE = os.path.join(ROOT, ".env")


def load_env(path=ENV_FILE):
    """Read KEY=VALUE lines into a dict. Never prints or logs values."""
    out = {}
    if not os.path.exists(path):
        return out
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            out[key.strip()] = value.strip().strip('"').strip("'")
    return out


def llm_settings(env=None):
    if env is None:
        env = load_env()
        for key, value in env.items():
            os.environ.setdefault(key, value)
    return {
        "base_url": os.environ.get("LLM_BASE_URL", "").rstrip("/"),
        "api_key": os.environ.get("LLM_API_KEY", ""),
        "model": os.environ.get("LLM_MODEL", ""),
    }


def configured(settings=None):
    s = settings or llm_settings()
    return bool(s["base_url"] and s["api_key"] and s["model"])


class LLMError(RuntimeError):
    pass


def chat(messages, settings=None, max_tokens=2000, timeout=90):
    """One chat completion. Returns the assistant text."""
    s = settings or llm_settings()
    if not configured(s):
        raise LLMError("LLM_BASE_URL / LLM_API_KEY / LLM_MODEL are not configured "
                       "(put them in .env or use --offline)")
    budget = max_tokens
    last = ""
    for attempt in range(2):
        body = json.dumps({
            "model": s["model"],
            "max_tokens": budget,
            "temperature": 0,
            "messages": messages,
        }).encode("utf-8")
        req = urllib.request.Request(
            s["base_url"] + "/chat/completions", data=body,
            headers={"Authorization": "Bearer " + s["api_key"],
                     "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8", "replace"))
        except urllib.error.HTTPError as exc:
            raise LLMError("HTTP %s from the endpoint: %s" % (exc.code, exc.read()[:200]))
        except Exception as exc:                      # noqa: BLE001 - reported, not hidden
            raise LLMError("could not reach %s: %s" % (s["base_url"], exc))
        choice = (data.get("choices") or [{}])[0]
        text = (choice.get("message") or {}).get("content") or ""
        if text.strip():
            return text
        last = "finish_reason=%s" % choice.get("finish_reason")
        if choice.get("finish_reason") != "length":
            break
        budget *= 2
    raise LLMError("the endpoint returned no text (%s)" % last)


SYSTEM_PROMPT = """You read one announcement page and return a JSON proposal.

Rules:
1. Reply with JSON only. No prose, no markdown fence.
2. Every value MUST be accompanied by `evidence`: a verbatim quote copied from the
   page, long enough to contain the value you report. If you cannot quote it,
   do not report it.
3. Never compute, convert, round or restate a number. Copy the wording of the page.
4. If the page does not state something, use null (or omit it from the list).
   Never guess. Do not fill a gap.

Schema:
{
  "title":        {"value": "...", "evidence": "..."},
  "organizer":    {"value": "...", "evidence": "..."},
  "submission_channel": {"value": "...", "evidence": "..."},
  "eligibility":  {"value": "...", "evidence": "..."},
  "key_dates": [{"label": "short label", "value": "the date as written",
                 "evidence": "..."}],
  "prizes":    [{"place": "the wording used on the page", "amount": "as written",
                 "currency": "as written or null", "evidence": "..."}],
  "deliverables": [{"value": "one required item", "evidence": "..."}]
}"""


def propose(source, settings=None, max_tokens=2500):
    """Ask the model for a proposal. Returns (raw_dict, raw_text)."""
    user = "Announcement page:\n<<<\n%s\n>>>" % source
    text = chat([{"role": "system", "content": SYSTEM_PROMPT},
                 {"role": "user", "content": user}],
                settings=settings, max_tokens=max_tokens)
    return parse_json(text), text


def parse_json(text):
    """Pull the JSON object out of a reply that may be fenced or padded."""
    if not text:
        raise LLMError("empty reply")
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    candidate = fenced.group(1) if fenced else None
    if candidate is None:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            candidate = text[start:end + 1]
    if candidate is None:
        raise LLMError("no JSON object in the reply")
    try:
        return json.loads(candidate)
    except ValueError as exc:
        raise LLMError("the reply was not valid JSON: %s" % exc)
