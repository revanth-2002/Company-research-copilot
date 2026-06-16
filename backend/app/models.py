from pydantic import BaseModel, Field, HttpUrl


class SessionCreate(BaseModel):
    company_name: str = Field(min_length=2, max_length=160)
    website: HttpUrl
    objective: str = Field(min_length=5, max_length=800)

    auto_run: bool = True


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1500)


class ChatResponse(BaseModel):
    answer: str


class SessionSummary(BaseModel):
    id: str
    user_id: str
    company_name: str
    website: str
    objective: str
    status: str
    created_at: str
    updated_at: str


class SessionDetail(SessionSummary):
    progress: list[dict] = []
    report: dict | None = None
    errors: list[str] = []
    chat: list[dict] = []
