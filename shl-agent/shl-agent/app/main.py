from typing import List, Literal, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .agent import handle_turn

app = FastAPI(title="SHL Assessment Recommender")


class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    messages: List[Message] = Field(..., min_length=1)


class Recommendation(BaseModel):
    name: str
    url: str
    test_type: str = ""


class ChatResponse(BaseModel):
    reply: str
    recommendations: List[Recommendation] = []
    end_of_conversation: bool = False


MAX_TURNS = 8


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    messages = [m.model_dump() for m in req.messages]

    if len(messages) > MAX_TURNS:
        messages = messages[-MAX_TURNS:]

    if len(messages) >= MAX_TURNS:
        # force a conclusion on the last allowed turn to respect the turn cap
        from .retrieval import catalog_index
        from .agent import analyze, draft_reply

        analysis = analyze(messages)
        query = analysis.get("search_query") or messages[-1]["content"]
        results = catalog_index.retrieve(query, k=10) or catalog_index.retrieve(
            messages[-1]["content"], k=5
        )
        recs = [
            {"name": r["name"], "url": r["url"], "test_type": r.get("test_type", "")}
            for r in results
        ]
        return ChatResponse(
            reply="Here is my best shortlist based on everything discussed so far.",
            recommendations=recs,
            end_of_conversation=True,
        )

    try:
        result = handle_turn(messages)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent error: {e}")

    return ChatResponse(**result)
