import asyncio
import json
from pathlib import Path

from inspect_ai.model import ChatMessageAssistant, ChatMessageTool, ChatMessageUser
from inspect_ai.tool import ToolCall
from inspect_scout import Transcript, transcripts_db


def flatten(value, indent=""):
    if isinstance(value, dict):
        lines = []
        for k, v in value.items():
            if isinstance(v, (dict, list)):
                lines.append(f"{indent}{k.replace('_', ' ')}:")
                lines.append(flatten(v, indent + "  "))
            else:
                lines.append(f"{indent}{k.replace('_', ' ')}: {v}")
        return "\n".join(lines)
    if isinstance(value, list):
        return "\n".join(f"{indent}- {flatten(v, indent + '  ').lstrip()}" for v in value)
    return f"{indent}{value}"


def clean_text(text):
    s = text.strip()
    if s.startswith("{"):
        try:
            obj = json.loads(s)
        except ValueError:
            return s
        if isinstance(obj, dict):
            msg = obj.pop("message", None)
            parts = [msg.strip()] if isinstance(msg, str) else []
            if obj:
                parts.append(flatten(obj))
            s = "\n\n".join(parts)
    return s


def to_messages(sim):
    out = []
    for m in sim["messages"]:
        content = m.get("content") or ""
        if m["role"] != "tool":
            content = clean_text(content)
        if m["role"] == "assistant":
            calls = [ToolCall(id=c.get("id") or f"{m.get('turn_idx')}_{j}", function=c["name"], arguments=c["arguments"])
                     for j, c in enumerate(m.get("tool_calls") or [])]
            out.append(ChatMessageAssistant(content=content, tool_calls=calls or None))
        elif m["role"] == "user":
            out.append(ChatMessageUser(content=content))
        elif m["role"] == "tool":
            out.append(ChatMessageTool(content=str(content), tool_call_id=m.get("id")))
    return out


def transcripts(results_json):
    data = json.loads(Path(results_json).read_text(encoding="utf-8"))
    info = data.get("info", {})
    model = (info.get("agent_info") or {}).get("llm") or Path(results_json).stem
    domain = (info.get("environment_info") or {}).get("domain_name", "tau2")
    for s in data["simulations"]:
        msgs = to_messages(s)
        yield Transcript(
            transcript_id=f"{model}_{s['task_id']}_{s['trial']}".replace("/", "_").replace(":", "_"),
            source_type=f"tau2-{domain}", source_id=str(s["id"]), task_id=str(s["task_id"]), model=model,
            message_count=len(msgs), messages=msgs,
            metadata={"trial": s["trial"], "reward": (s.get("reward_info") or {}).get("reward")})


def import_tau2(results_json, db):
    async def run():
        async def items():
            for t in transcripts(results_json):
                yield t

        async with transcripts_db(str(Path(db).resolve())) as store:
            await store.insert(items())

    asyncio.run(run())
