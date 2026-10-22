from pydantic import BaseModel


class ErrorResponse(BaseModel):
    code: str
    message: str
    fields: dict[str, str] | None = None


class MessageResponse(BaseModel):
    message: str
