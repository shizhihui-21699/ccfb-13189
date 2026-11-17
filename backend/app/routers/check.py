from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..detector import evaluate
from ..schemas import CheckRequest, CheckResponse

router = APIRouter(prefix="/api/check", tags=["check"])


@router.post("/registration", response_model=CheckResponse)
def check_registration(req: CheckRequest, db: Session = Depends(get_db)):
    """注册环节调用:返回放行/人工审核/拦截,以及是否允许领券。

    业务侧用法:
      decision=allow  -> 正常注册并发券
      decision=review -> 注册挂起转人工审核,不发券(coupon_allowed=false)
      decision=block  -> 直接拒绝注册
    """
    record = evaluate(req.email, req.phone, req.ip, db)
    return CheckResponse(
        check_id=record.id,
        decision=record.decision,
        coupon_allowed=record.coupon_allowed,
        review_required=record.decision == "review",
        reasons=record.reasons,
        email_score=record.email_score,
        phone_score=record.phone_score,
    )
