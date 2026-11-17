from typing import List, Optional

from pydantic import BaseModel, Field


class CheckRequest(BaseModel):
    email: str = ""
    phone: str = ""
    ip: str = ""


class Reason(BaseModel):
    code: str
    message: str


class CheckResponse(BaseModel):
    check_id: int
    decision: str            # allow / review / block
    coupon_allowed: bool
    review_required: bool
    reasons: List[Reason]
    email_score: int
    phone_score: int


class EmailDomainIn(BaseModel):
    domain: str
    category: str = "disposable"
    note: str = ""


class EmailDomainPatch(BaseModel):
    enabled: Optional[bool] = None
    category: Optional[str] = None
    note: Optional[str] = None


class PhonePrefixIn(BaseModel):
    prefix: str
    kind: str = "virtual_carrier"
    label: str = ""
    note: str = ""


class PhonePrefixPatch(BaseModel):
    enabled: Optional[bool] = None
    kind: Optional[str] = None
    label: Optional[str] = None
    note: Optional[str] = None


class ReviewAction(BaseModel):
    action: str = Field(pattern="^(approve|reject)$")
    reviewer: str = "admin"
    note: str = ""


class CandidateAction(BaseModel):
    # confirm 时可指定落入名单的分类
    category: str = "disposable"
    note: str = ""
