"""一次性邮箱新域名发现。

四路互补的发现机制:
1. 公开名单同步  —— 定时拉取开源一次性域名列表(GitHub 社区维护), diff 入库
2. 行为突发检测  —— 自身注册流水里,未知名域名短时大量注册 -> 候选
3. DNS 指纹      —— 候选域名的 MX 指向已知一次性邮箱服务商 / 域名注册时间很新(RDAP)
4. 命名特征      —— 含 temp/tmp/trash 等特征词的新域名直接进候选

候选进入 DomainCandidate 队列,运营在后台确认后一键落入正式名单。
"""
import asyncio
import re
from datetime import datetime, timedelta
from typing import Dict, List

import dns.resolver
import httpx
from sqlalchemy import func
from sqlalchemy.orm import Session

from .detector import DISPOSABLE_KEYWORDS, normalize_email
from .models import DomainCandidate, EmailDomain, RegistrationCheck

PUBLIC_LISTS = [
    # 社区维护最活跃的一次性域名名单
    "https://raw.githubusercontent.com/disposable-email-domains/disposable-email-domains/master/disposable_email_blocklist.conf",
    "https://raw.githubusercontent.com/7c/fakefilter/main/txt/data.txt",
]

# 已知一次性邮箱服务的 MX/基础设施指纹
DISPOSABLE_MX_FINGERPRINTS = [
    "mailinator", "tempmail", "temp-mail", "mailsac", "yopmail",
    "guerrillamail", "sharklasers", "mohmal", "maildrop", "getnada",
    "inboxbear", "emailondeck", "tmpmail", "fakemail",
]

DOMAIN_RE = re.compile(r"^(?=.{1,253}$)([a-z0-9](-?[a-z0-9])*\.)+[a-z]{2,}$")


def _upsert_candidate(db: Session, domain: str, reason: str,
                      evidence: dict, source: str = "auto") -> bool:
    """已存在则累加 hits 与证据,返回是否新建"""
    domain = domain.lower().strip()
    if not DOMAIN_RE.match(domain):
        return False
    exists_blocklist = (db.query(EmailDomain)
                        .filter(EmailDomain.domain == domain).first())
    if exists_blocklist:
        return False
    cand = (db.query(DomainCandidate)
            .filter(DomainCandidate.domain == domain).first())
    if cand:
        cand.hits += 1
        cand.last_seen = datetime.utcnow()
        merged = dict(cand.evidence or {})
        merged.update(evidence)
        merged.setdefault("reasons", [])
        if reason not in merged["reasons"]:
            merged["reasons"].append(reason)
        cand.evidence = merged
        return False
    db.add(DomainCandidate(
        domain=domain, reason=reason, source=source,
        evidence={**evidence, "reasons": [reason]},
    ))
    return True


# ---------- 1. 公开名单同步 ----------

async def sync_public_lists(db: Session) -> Dict:
    added, skipped, failed = 0, 0, []
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        for url in PUBLIC_LISTS:
            try:
                resp = await client.get(url)
                resp.raise_for_status()
            except Exception as e:  # 网络失败不阻断其他源
                failed.append({"url": url, "error": str(e)})
                continue
            for line in resp.text.splitlines():
                domain = line.strip().lower()
                if not domain or domain.startswith("#") or not DOMAIN_RE.match(domain):
                    continue
                if db.query(EmailDomain).filter(EmailDomain.domain == domain).first():
                    skipped += 1
                    continue
                db.add(EmailDomain(domain=domain, category="disposable",
                                   source="public-list",
                                   note=f"synced from {url.split('/')[4]}"))
                added += 1
    db.commit()
    return {"added": added, "skipped_existing": skipped, "failed_sources": failed}


# ---------- 2. 行为突发检测 ----------

def scan_registration_bursts(db: Session, window_hours: int = 24,
                             min_regs: int = 5) -> Dict:
    """未知名域名在时间窗内注册量突增 -> 候选"""
    since = datetime.utcnow() - timedelta(hours=window_hours)
    known = {d.domain for d in db.query(EmailDomain.domain).all()}
    known |= {c.domain for c in
              db.query(DomainCandidate.domain)
              .filter(DomainCandidate.status == "rejected").all()}

    rows = (db.query(RegistrationCheck.email_domain,
                     func.count(RegistrationCheck.id).label("cnt"),
                     func.count(func.distinct(RegistrationCheck.ip)).label("ips"))
            .filter(RegistrationCheck.created_at >= since,
                    RegistrationCheck.email_domain != "")
            .group_by(RegistrationCheck.email_domain)
            .having(func.count(RegistrationCheck.id) >= min_regs)
            .all())

    new_candidates = 0
    for domain, cnt, ips in rows:
        if domain in known:
            continue
        if _upsert_candidate(db, domain, "registration_burst",
                             {"regs_in_window": cnt, "distinct_ips": ips,
                              "window_hours": window_hours}):
            new_candidates += 1
        else:
            cand = db.query(DomainCandidate).filter(
                DomainCandidate.domain == domain).first()
            if cand:
                cand.reg_count_24h = cnt
    db.commit()
    return {"scanned_domains": len(rows), "new_candidates": new_candidates}


# ---------- 3. DNS / RDAP 指纹探测 ----------

def _mx_hosts(domain: str) -> List[str]:
    try:
        answers = dns.resolver.resolve(domain, "MX", lifetime=5)
        return [str(r.exchange).lower().rstrip(".") for r in answers]
    except Exception:
        return []


async def _rdap_age_days(domain: str) -> int:
    """通过 RDAP 查域名注册时间,失败返回 -1"""
    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            resp = await client.get(f"https://rdap.org/domain/{domain}")
            if resp.status_code != 200:
                return -1
            for ev in resp.json().get("events", []):
                if ev.get("eventAction") == "registration":
                    dt = datetime.fromisoformat(
                        ev["eventDate"].replace("Z", "+00:00"))
                    return (datetime.now(dt.tzinfo) - dt).days
    except Exception:
        pass
    return -1


async def probe_candidates(db: Session, limit: int = 50) -> Dict:
    """对 pending 候选做 MX 指纹 + 域名年龄探测,补证据、提置信"""
    cands = (db.query(DomainCandidate)
             .filter(DomainCandidate.status == "pending")
             .order_by(DomainCandidate.hits.desc())
             .limit(limit).all())
    mx_hit, young = 0, 0
    for cand in cands:
        evidence = dict(cand.evidence or {})
        mx = await asyncio.to_thread(_mx_hosts, cand.domain)
        if mx:
            evidence["mx"] = mx
            for host in mx:
                for fp in DISPOSABLE_MX_FINGERPRINTS:
                    if fp in host:
                        evidence["mx_fingerprint"] = fp
                        cand.reason = "disposable_mx"
                        cand.hits += 5  # 强信号,排前
                        mx_hit += 1
                        break
        age = await _rdap_age_days(cand.domain)
        if age >= 0:
            evidence["domain_age_days"] = age
            if age <= 180:
                cand.hits += 2
                young += 1
        cand.evidence = evidence
    db.commit()
    return {"probed": len(cands), "mx_fingerprint_hits": mx_hit,
            "young_domains": young}


# ---------- 4. 命名特征扫描 ----------

def scan_keyword_domains(db: Session, window_hours: int = 24) -> Dict:
    """注册流水中出现含特征词的未知名域名 -> 候选"""
    since = datetime.utcnow() - timedelta(hours=window_hours)
    domains = {r[0] for r in
               db.query(RegistrationCheck.email_domain)
               .filter(RegistrationCheck.created_at >= since,
                       RegistrationCheck.email_domain != "")
               .distinct().all()}
    known = {d.domain for d in db.query(EmailDomain.domain).all()}
    new_candidates = 0
    for domain in domains:
        if domain in known:
            continue
        for kw in DISPOSABLE_KEYWORDS:
            if kw in domain:
                if _upsert_candidate(db, domain, "keyword",
                                     {"matched_keyword": kw}):
                    new_candidates += 1
                break
    db.commit()
    return {"scanned_domains": len(domains), "new_candidates": new_candidates}


async def run_full_discovery(db: Session) -> Dict:
    """一键跑完整发现流程(同步名单 -> 行为 -> 特征 -> 指纹探测)"""
    sync_result = await sync_public_lists(db)
    burst = scan_registration_bursts(db)
    keyword = scan_keyword_domains(db)
    probe = await probe_candidates(db)
    return {"public_list_sync": sync_result, "burst_scan": burst,
            "keyword_scan": keyword, "probe": probe}
