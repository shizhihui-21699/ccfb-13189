from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from .. import discovery
from ..database import get_db
from ..models import DomainCandidate, EmailDomain, PhonePrefix, RegistrationCheck
from ..schemas import (CandidateAction, EmailDomainIn, EmailDomainPatch,
                       PhonePrefixIn, PhonePrefixPatch, ReviewAction)

router = APIRouter(prefix="/api/admin", tags=["admin"])


# ---------- 邮箱域名名单 ----------

@router.get("/email-domains")
def list_email_domains(q: str = "", enabled: Optional[bool] = None,
                       page: int = 1, size: int = Query(20, le=200),
                       db: Session = Depends(get_db)):
    query = db.query(EmailDomain)
    if q:
        query = query.filter(EmailDomain.domain.contains(q.lower()))
    if enabled is not None:
        query = query.filter(EmailDomain.enabled.is_(enabled))
    total = query.count()
    items = (query.order_by(EmailDomain.id.desc())
             .offset((page - 1) * size).limit(size).all())
    return {"total": total, "items": [_domain_dict(d) for d in items]}


@router.post("/email-domains", status_code=201)
def add_email_domain(body: EmailDomainIn, db: Session = Depends(get_db)):
    domain = body.domain.strip().lower().rstrip(".")
    if db.query(EmailDomain).filter(EmailDomain.domain == domain).first():
        raise HTTPException(409, "域名已存在")
    d = EmailDomain(domain=domain, category=body.category,
                    source="manual", note=body.note)
    db.add(d)
    db.commit()
    db.refresh(d)
    return _domain_dict(d)


@router.patch("/email-domains/{item_id}")
def patch_email_domain(item_id: int, body: EmailDomainPatch,
                       db: Session = Depends(get_db)):
    d = db.get(EmailDomain, item_id)
    if not d:
        raise HTTPException(404, "not found")
    for field in ("enabled", "category", "note"):
        val = getattr(body, field)
        if val is not None:
            setattr(d, field, val)
    db.commit()
    return _domain_dict(d)


@router.delete("/email-domains/{item_id}", status_code=204)
def delete_email_domain(item_id: int, db: Session = Depends(get_db)):
    d = db.get(EmailDomain, item_id)
    if not d:
        raise HTTPException(404, "not found")
    db.delete(d)
    db.commit()


def _domain_dict(d: EmailDomain) -> dict:
    return {"id": d.id, "domain": d.domain, "category": d.category,
            "source": d.source, "enabled": d.enabled, "note": d.note,
            "created_at": d.created_at.isoformat() if d.created_at else None}


# ---------- 手机号段名单 ----------

@router.get("/phone-prefixes")
def list_phone_prefixes(q: str = "", db: Session = Depends(get_db)):
    query = db.query(PhonePrefix)
    if q:
        query = query.filter(PhonePrefix.prefix.contains(q))
    items = query.order_by(PhonePrefix.prefix).all()
    return {"total": len(items), "items": [_prefix_dict(p) for p in items]}


@router.post("/phone-prefixes", status_code=201)
def add_phone_prefix(body: PhonePrefixIn, db: Session = Depends(get_db)):
    prefix = body.prefix.strip()
    if db.query(PhonePrefix).filter(PhonePrefix.prefix == prefix).first():
        raise HTTPException(409, "号段已存在")
    p = PhonePrefix(prefix=prefix, kind=body.kind, label=body.label,
                    note=body.note)
    db.add(p)
    db.commit()
    db.refresh(p)
    return _prefix_dict(p)


@router.patch("/phone-prefixes/{item_id}")
def patch_phone_prefix(item_id: int, body: PhonePrefixPatch,
                       db: Session = Depends(get_db)):
    p = db.get(PhonePrefix, item_id)
    if not p:
        raise HTTPException(404, "not found")
    for field in ("enabled", "kind", "label", "note"):
        val = getattr(body, field)
        if val is not None:
            setattr(p, field, val)
    db.commit()
    return _prefix_dict(p)


@router.delete("/phone-prefixes/{item_id}", status_code=204)
def delete_phone_prefix(item_id: int, db: Session = Depends(get_db)):
    p = db.get(PhonePrefix, item_id)
    if not p:
        raise HTTPException(404, "not found")
    db.delete(p)
    db.commit()


def _prefix_dict(p: PhonePrefix) -> dict:
    return {"id": p.id, "prefix": p.prefix, "kind": p.kind, "label": p.label,
            "enabled": p.enabled, "note": p.note,
            "created_at": p.created_at.isoformat() if p.created_at else None}


# ---------- 人工审核队列 ----------

@router.get("/reviews")
def list_reviews(status: str = "pending", page: int = 1,
                 size: int = Query(20, le=100), db: Session = Depends(get_db)):
    query = db.query(RegistrationCheck).filter(
        RegistrationCheck.review_status == status)
    total = query.count()
    items = (query.order_by(RegistrationCheck.id.desc())
             .offset((page - 1) * size).limit(size).all())
    return {"total": total, "items": [_check_dict(c) for c in items]}


@router.post("/reviews/{check_id}")
def resolve_review(check_id: int, body: ReviewAction,
                   db: Session = Depends(get_db)):
    c = db.get(RegistrationCheck, check_id)
    if not c:
        raise HTTPException(404, "not found")
    if c.review_status != "pending":
        raise HTTPException(400, "该记录已审核")
    c.review_status = "approved" if body.action == "approve" else "rejected"
    c.reviewer = body.reviewer
    c.review_note = body.note
    c.reviewed_at = datetime.utcnow()
    # 人工放行 -> 允许补发券;人工拒绝 -> 保持禁券
    c.coupon_allowed = body.action == "approve"
    db.commit()
    return _check_dict(c)


def _check_dict(c: RegistrationCheck) -> dict:
    return {"id": c.id, "created_at": c.created_at.isoformat(),
            "email": c.email, "email_domain": c.email_domain,
            "phone": c.phone, "ip": c.ip, "decision": c.decision,
            "coupon_allowed": c.coupon_allowed, "reasons": c.reasons,
            "email_score": c.email_score, "phone_score": c.phone_score,
            "review_status": c.review_status, "reviewer": c.reviewer}


# ---------- 新域名发现 ----------

@router.get("/candidates")
def list_candidates(status: str = "pending", page: int = 1,
                    size: int = Query(20, le=100), db: Session = Depends(get_db)):
    query = db.query(DomainCandidate).filter(DomainCandidate.status == status)
    total = query.count()
    items = (query.order_by(DomainCandidate.hits.desc(),
                            DomainCandidate.last_seen.desc())
             .offset((page - 1) * size).limit(size).all())
    return {"total": total, "items": [_cand_dict(c) for c in items]}


@router.post("/candidates/{cand_id}/confirm")
def confirm_candidate(cand_id: int, body: CandidateAction,
                      db: Session = Depends(get_db)):
    c = db.get(DomainCandidate, cand_id)
    if not c:
        raise HTTPException(404, "not found")
    c.status = "confirmed"
    if not db.query(EmailDomain).filter(EmailDomain.domain == c.domain).first():
        db.add(EmailDomain(domain=c.domain, category=body.category,
                           source="discovery",
                           note=body.note or f"自动发现({c.reason})"))
    db.commit()
    return _cand_dict(c)


@router.post("/candidates/{cand_id}/reject")
def reject_candidate(cand_id: int, db: Session = Depends(get_db)):
    c = db.get(DomainCandidate, cand_id)
    if not c:
        raise HTTPException(404, "not found")
    c.status = "rejected"
    db.commit()
    return _cand_dict(c)


@router.post("/discovery/run")
async def run_discovery(db: Session = Depends(get_db)):
    """手动触发完整发现流程;生产环境建议再加定时任务(cron/celery beat)"""
    return await discovery.run_full_discovery(db)


@router.post("/discovery/sync-lists")
async def sync_lists(db: Session = Depends(get_db)):
    return await discovery.sync_public_lists(db)


@router.post("/discovery/scan")
async def scan_only(db: Session = Depends(get_db)):
    burst = discovery.scan_registration_bursts(db)
    keyword = discovery.scan_keyword_domains(db)
    probe = await discovery.probe_candidates(db)
    return {"burst_scan": burst, "keyword_scan": keyword, "probe": probe}


def _cand_dict(c: DomainCandidate) -> dict:
    return {"id": c.id, "domain": c.domain, "reason": c.reason,
            "evidence": c.evidence, "hits": c.hits,
            "reg_count_24h": c.reg_count_24h, "status": c.status,
            "first_seen": c.first_seen.isoformat() if c.first_seen else None,
            "last_seen": c.last_seen.isoformat() if c.last_seen else None}
