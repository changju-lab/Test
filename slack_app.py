import hashlib
import hmac
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Request
from langchain_chroma import Chroma
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langgraph.prebuilt import create_react_agent
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

load_dotenv()
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

SLACK_BOT_TOKEN = os.environ["SLACK_BOT_TOKEN"]
SLACK_SIGNING_SECRET = os.environ["SLACK_SIGNING_SECRET"]
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]

CHROMA_DIR = Path(__file__).resolve().parent.parent / "16일차_실습" / "chroma_regulations"
if not CHROMA_DIR.exists():
    raise FileNotFoundError(
        f"{CHROMA_DIR} 없음. 16.4 노트북에서 Chroma 인덱싱을 먼저 완료하세요."
    )

_embedding = OpenAIEmbeddings(model="text-embedding-3-small", api_key=OPENAI_API_KEY)
_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, api_key=OPENAI_API_KEY)
_vectorstore = Chroma(persist_directory=str(CHROMA_DIR), embedding_function=_embedding)


@tool
def search_regulations(query: str) -> str:
    """학부·대학원 학칙 문서에서 관련 조항을 검색합니다."""
    docs = _vectorstore.similarity_search(query, k=3)
    if not docs:
        return "관련 문서를 찾지 못했습니다."
    return "\n\n".join(
        f"[{d.metadata.get('level', '?')}] {d.page_content[:600]}" for d in docs
    )


_agent = create_react_agent(
    _llm,
    [search_regulations],
    prompt=(
        "당신은 학부·대학원 학칙 안내 봇입니다. "
        "search_regulations로 문서를 검색한 뒤, 검색 결과만 근거로 한국어로 간결히 답하세요. "
        "도구는 최대 2번만 호출하세요."
    ),
)


def run_agent(question: str) -> str:
    result = _agent.invoke(
        {"messages": [HumanMessage(content=question)]},
        config={"recursion_limit": 10},
    )
    answer = result["messages"][-1].content
    if answer.startswith("Sorry, need more steps"):
        return _rag_answer(question)
    return answer


def _rag_answer(question: str) -> str:
    """ponytail: ReAct가 실패하면 17.1식 단순 RAG로 폴백"""
    docs = _vectorstore.similarity_search(question, k=3)
    if not docs:
        return "관련 학칙을 찾지 못했습니다."
    context = "\n\n".join(d.page_content[:600] for d in docs)
    prompt = (
        "아래 학칙 발췌만 근거로 질문에 두세 문장으로 답하세요.\n"
        "근거에 없으면 추측하지 마세요.\n\n"
        f"문서:\n{context}\n\n질문: {question}"
    )
    return _llm.invoke(prompt).content


client = WebClient(token=SLACK_BOT_TOKEN)
app = FastAPI(title="Slack RAG Agent Bot")
_seen: set[str] = set()


def verify_slack_signature(body: bytes, timestamp: str | None, signature: str | None) -> None:
    if not timestamp or not signature:
        raise HTTPException(status_code=401, detail="missing signature headers")
    if abs(time.time() - int(timestamp)) > 60 * 5:
        raise HTTPException(status_code=401, detail="stale request")
    base = f"v0:{timestamp}:{body.decode('utf-8')}"
    digest = hmac.new(
        SLACK_SIGNING_SECRET.encode(),
        base.encode(),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(f"v0={digest}", signature):
        raise HTTPException(status_code=401, detail="invalid signature")


def reply_with_agent(channel: str, text: str, thread_ts: str | None = None) -> None:
    print("받은 메시지:", text)
    try:
        answer = run_agent(text)
    except Exception as e:
        answer = f"답변 생성 중 오류가 발생했습니다: {e}"
        print("agent 실패:", e)
    try:
        kwargs: dict = {"channel": channel, "text": answer}
        if thread_ts:
            kwargs["thread_ts"] = thread_ts
        client.chat_postMessage(**kwargs)
    except SlackApiError as e:
        print("postMessage 실패:", e.response.get("error"))


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/slack/events")
async def slack_events(
    request: Request,
    background_tasks: BackgroundTasks,
    x_slack_signature: str | None = Header(default=None),
    x_slack_request_timestamp: str | None = Header(default=None),
):
    body = await request.body()
    verify_slack_signature(body, x_slack_request_timestamp, x_slack_signature)
    payload = await request.json()

    if payload.get("type") == "url_verification":
        return {"challenge": payload.get("challenge")}

    if payload.get("type") != "event_callback":
        return {"ok": True}

    event_id = payload.get("event_id")
    if event_id:
        if event_id in _seen:
            return {"ok": True}
        _seen.add(event_id)

    event = payload.get("event") or {}
    if event.get("bot_id") or event.get("subtype") == "bot_message":
        return {"ok": True}

    text = (event.get("text") or "").strip()
    channel = event.get("channel")
    if not text or not channel:
        return {"ok": True}

    if event.get("type") == "app_mention":
        parts = text.split(maxsplit=1)
        text = parts[1] if len(parts) > 1 else text

    if not text:
        return {"ok": True}

    # ponytail: Slack은 3초 안에 200 응답 필요 — Agent는 백그라운드에서 실행
    background_tasks.add_task(reply_with_agent, channel, text, event.get("ts"))
    return {"ok": True}
