import re
from typing import Literal

from pydantic import BaseModel, field_validator

_DOMAIN_RE = re.compile(
    r"^(?=.{1,253}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$"
)


class HookPayload(BaseModel):
    status: Literal["success", "failed"]
    domain: str

    @field_validator("domain")
    @classmethod
    def validate_domain(cls, v: str) -> str:
        v = v.strip().lower()
        if not _DOMAIN_RE.match(v):
            raise ValueError("invalid domain name")
        return v


class HookResponse(BaseModel):
    ok: bool = True
    status: str
    domain: str
