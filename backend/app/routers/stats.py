from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import DomainCandidate, EmailDomain, PhonePrefix, RegistrationCheck

router = APIRouter(prefix="/api/admin/stats", tags=["stats"])


@router.get("/overview")
def overview(db: Session = Depends(get_db)):
    today = datetime.utcnow().date()
    today_start = datetime.combine(today, datetime.min.time())

    def count(decision=None, since=None):
        q = db.query(func.count(RegistrationCheck.id))
        if decision:
            q = q.filter(RegistrationCheck.decision == decision)
        if since:
            q = q.filter(RegistrationCheck.created_at >= since)
        return q.scalar() or 0

    return {
        "today": {
            "total": count(since=today_start),
            "allow": count("allow", today_start),
            "review": count("review", today_start),
            "block": count("block", today_start),
            "coupon_blocked": (db.query(func.count(RegistrationCheck.id))
                               .filter(RegistrationCheck.created_at >= today_start,
                                       RegistrationCheck.coupon_allowed.is_(False))
                               .scalar() or 0),
        },
        "total": {
            "checks": count(),
            "allow": count("allow"),
            "review": count("review"),
            "block": count("block"),
        },
        "lists": {
            "email_domains": db.query(func.count(EmailDomain.id))
                               .filter(EmailDomain.enabled.is_(True)).scalar(),
            "phone_prefixes": db.query(func.count(PhonePrefix.id))
                               .filter(PhonePrefix.enabled.is_(True)).scalar(),
            "pending_candidates": db.query(func.count(DomainCandidate.id))
                .filter(DomainCandidate.status == "pending").scalar(),
            "pending_reviews": db.query(func.count(RegistrationCheck.id))
                .filter(RegistrationCheck.review_status == "pending").scalar(),
        },
    }


@router.get("/daily")
def daily(days: int = Query(30, le=90), db: Session = Depends(get_db)):
    since = datetime.utcnow() - timedelta(days=days)
    day_col = func.date(RegistrationCheck.created_at)
    rows = (db.query(day_col.label("day"),
                     RegistrationCheck.decision,
                     func.count(RegistrationCheck.id).label("cnt"))
            .filter(RegistrationCheck.created_at >= since)
            .group_by(day_col, RegistrationCheck.decision)
            .order_by(day_col)
            .all())
    result = {}
    for day, decision, cnt in rows:
        result.setdefault(str(day), {"allow": 0, "review": 0, "block": 0})
        result[str(day)][decision] = cnt
    return {"days": [{"date": d, **v} for d, v in sorted(result.items())]}


@router.get("/top-domains")
def top_domains(days: int = Query(7, le=90), limit: int = 10,
                db: Session = Depends(get_db)):
    """拦截/审核最多的邮箱域,帮运营判断哪些域名最值得确认进名单"""
    since = datetime.utcnow() - timedelta(days=days)
    rows = (db.query(RegistrationCheck.email_domain,
                     func.count(RegistrationCheck.id).label("cnt"))
            .filter(RegistrationCheck.created_at >= since,
                    RegistrationCheck.decision != "allow",
                    RegistrationCheck.email_domain != "")
            .group_by(RegistrationCheck.email_domain)
            .order_by(func.count(RegistrationCheck.id).desc())
            .limit(limit).all())
    return {"items": [{"domain": d, "count": c} for d, c in rows]}


@router.get("/top-reasons")
def top_reasons(days: int = Query(7, le=90), db: Session = Depends(get_db)):
    """按命中原因统计(取每条记录的第一个原因码)"""
    since = datetime.utcnow() - timedelta(days=days)
    rows = (db.query(RegistrationCheck.reasons)
            .filter(RegistrationCheck.created_at >= since,
                    RegistrationCheck.decision != "allow")
            .all())
    counter = {}
    for (reasons,) in rows:
        for r in (reasons or [])[:1]:
            code = r.get("code", "unknown")
            counter[code] = counter.get(code, 0) + 1
    items = sorted(counter.items(), key=lambda x: -x[1])
    return {"items": [{"code": k, "count": v} for k, v in items]}
