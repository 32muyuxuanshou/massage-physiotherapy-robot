from typing import Any, Optional
from pydantic import BaseModel


class ResponseModel(BaseModel):
    code: int = 200
    message: str = "success"
    data: Optional[Any] = None


def success_response(data: Any = None, message: str = "success") -> ResponseModel:
    return ResponseModel(code=200, message=message, data=data)


def error_response(code: int = 400, message: str = "error", data: Any = None) -> ResponseModel:
    return ResponseModel(code=code, message=message, data=data)
