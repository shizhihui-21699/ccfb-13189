"""注册临时身份识别引擎。

判定策略(可按业务调整 POLICY):
  - 命中一次性邮箱名单            -> review + 禁券
  - 邮箱域启发式评分 >= 阈值       -> review + 禁券
  - 命中虚拟运营商/物联网号段       -> review + 禁券
  - 命中接码平台号段               -> block
  - 邮箱与手机同时命中             -> block
  - 其余                          -> allow
"""
import math
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from .models import EmailDomain, PhonePrefix, RegistrationCheck

POLICY = {
    "email_heuristic_review_threshold": 60,  # 启发式评分达到即转人工
    "combo_block": True,                     # 邮箱+手机双命中直接拦截
}

# 一次性邮箱服务常用命名特征
DISPOSABLE_KEYWORDS = [
    "temp", "tmp", "trash", "junk", "fake", "throwaway", "disposable",
    "guerrilla", "mailinator", "yopmail", "sharklasers", "10min", "minutemail",
    "maildrop", "getnada", "mohmal", "burner", "spam", "anon", "temporary",
    "linshi", "yopmail", "mailnesia", "tempr", "discard", "spamgourmet",
    "fakemail", "tempmail", "tmpmail", "oneoff", "nowmymail", "emailondeck",
]

# 免费/滥用高发 TLD(Freenom 系及廉价新顶级域)
RISKY_TLDS = {
    "tk", "ml", "ga", "cf", "gq", "top", "xyz", "icu", "online", "site",
    "club", "work", "click", "link", "loan", "win", "bid", "stream", "quest",
}

# 常见正规邮箱域,命中后直接放行不参与启发式评分(防误伤)
FREEMAIL_WHITELIST = {
    "qq.com", "163.com", "126.com", "sina.com", "sohu.com", "aliyun.com",
    "139.com", "189.cn", "gmail.com", "outlook.com", "hotmail.com",
    "yahoo.com", "icloud.com", "foxmail.com", "yeah.net", "me.com",
    "proton.me", "protonmail.com", "aol.com", "zoho.com", "msn.com",
}


@dataclass
class FactorResult:
    score: int = 0
    reasons: List[dict] = field(default_factory=list)
    blocklist_hit: bool = False
    hit_kind: str = ""          # phone 命中的名单类型
    hard_block: bool = False

    def add(self, code: str, message: str, score: int = 0):
        self.reasons.append({"code": code, "message": message})
        self.score += score


def normalize_email(email: str) -> Tuple[str, str]:
    email = (email or "").strip().lower()
    if "@" not in email:
        return email, ""
    local, domain = email.rsplit("@", 1)
    # 去掉 +tag 与子地址,便于行为聚合
    local = local.split("+", 1)[0]
    return local, domain.strip().rstrip(".")


def domain_chain(domain: str) -> List[str]:
    """a.b.mailtemp.com -> [a.b.mailtemp.com, b.mailtemp.com, mailtemp.com]"""
    parts = domain.split(".")
    return [".".join(parts[i:]) for i in range(len(parts) - 1)]


def normalize_phone(phone: str) -> str:
    digits = re.sub(r"\D", "", phone or "")
    # 中国手机号去国家码
    if digits.startswith("86") and len(digits) == 13:
        digits = digits[2:]
    if digits.startswith("0086"):
        digits = digits[4:]
    return digits


def _entropy(s: str) -> float:
    if not s:
        return 0.0
    freq = {}
    for ch in s:
        freq[ch] = freq.get(ch, 0) + 1
    return -sum((c / len(s)) * math.log2(c / len(s)) for c in freq.values())


def _random_looking(label: str) -> bool:
    """判断域名单词是否像随机生成的:高熵 + 低元音比 + 含数字混杂"""
    label = re.sub(r"[^a-z0-9]", "", label)
    if len(label) < 6:
        return False
    vowels = sum(1 for c in label if c in "aeiou")
    digits = sum(1 for c in label if c.isdigit())
    vowel_ratio = vowels / len(label)
    return _entropy(label) > 3.2 and (vowel_ratio < 0.25 or digits >= 3)


def check_email(email: str, db: Session) -> FactorResult:
    res = FactorResult()
    local, domain = normalize_email(email)
    if not domain:
        res.add("email_invalid", "邮箱格式非法", 40)
        return res

    # 1. 名单匹配(含父域)
    enabled = {d.domain: d for d in db.query(EmailDomain).filter(EmailDomain.enabled.is_(True)).all()}
    for cand in domain_chain(domain):
        if cand in enabled:
            hit = enabled[cand]
            res.blocklist_hit = True
            res.add("email_blocklist",
                    f"邮箱域 {cand} 在{('一次性邮箱' if hit.category == 'disposable' else '高风险')}名单中",
                    100)
            return res

    if domain in FREEMAIL_WHITELIST:
        return res

    # 2. 启发式评分(用于还没进名单的新域名)
    labels = domain.split(".")
    sld = labels[-2] if len(labels) >= 2 else labels[0]
    tld = labels[-1]

    for kw in DISPOSABLE_KEYWORDS:
        if kw in domain:
            res.add("email_keyword", f"域名含一次性邮箱特征词 '{kw}'", 45)
            break
    if tld in RISKY_TLDS:
        res.add("email_risky_tld", f"使用滥用高发顶级域 .{tld}", 20)
    if _random_looking(sld):
        res.add("email_random_domain", f"域名 '{sld}' 疑似随机生成", 30)
    if re.fullmatch(r"[a-z]+mail\d*|\d+mail|mail\d+", sld):
        res.add("email_mail_pattern", "域名形如临时邮箱命名(xxxmail123)", 25)

    # 3. 行为信号:该域近期注册突发(自身数据反馈)
    since = datetime.utcnow() - timedelta(hours=24)
    recent = (db.query(func.count(RegistrationCheck.id))
              .filter(RegistrationCheck.email_domain == domain,
                      RegistrationCheck.created_at >= since)
              .scalar() or 0)
    if recent >= 10:
        res.add("email_domain_burst", f"该域名24小时内已有 {recent} 次注册", 35)
    elif recent >= 5:
        res.add("email_domain_burst", f"该域名24小时内已有 {recent} 次注册", 20)

    return res


def check_phone(phone: str, db: Session) -> FactorResult:
    res = FactorResult()
    digits = normalize_phone(phone)
    if not digits:
        return res
    if not (7 <= len(digits) <= 15):
        res.add("phone_invalid", "手机号长度异常", 30)
        return res

    prefixes = (db.query(PhonePrefix)
                .filter(PhonePrefix.enabled.is_(True))
                .order_by(func.length(PhonePrefix.prefix).desc())
                .all())
    for p in prefixes:
        if digits.startswith(p.prefix):
            res.hit_kind = p.kind
            if p.kind == "sms_platform":
                res.add("phone_sms_platform",
                        f"号码命中接码平台号段 {p.prefix}({p.label})", 100)
                res.hard_block = True
            elif p.kind == "virtual_carrier":
                res.add("phone_virtual_carrier",
                        f"号码属虚拟运营商号段 {p.prefix}({p.label})", 60)
            elif p.kind == "iot":
                res.add("phone_iot",
                        f"号码属物联网号段 {p.prefix}({p.label})", 50)
            return res
    return res


def evaluate(email: str, phone: str, ip: str, db: Session) -> RegistrationCheck:
    email_res = check_email(email, db)
    phone_res = check_phone(phone, db)

    _, domain = normalize_email(email)
    reasons = email_res.reasons + phone_res.reasons

    review = False
    block = phone_res.hard_block

    if email_res.blocklist_hit:
        review = True
    if email_res.score >= POLICY["email_heuristic_review_threshold"]:
        review = True
    if phone_res.hit_kind in ("virtual_carrier", "iot"):
        review = True
    if POLICY["combo_block"] and email_res.blocklist_hit and phone_res.hit_kind:
        block = True
        reasons.append({"code": "combo_hit", "message": "邮箱与手机号同时命中风险名单"})

    # 同 IP 短时批量注册:无论名单是否命中都升级
    if ip:
        since = datetime.utcnow() - timedelta(hours=1)
        ip_recent = (db.query(func.count(RegistrationCheck.id))
                     .filter(RegistrationCheck.ip == ip,
                             RegistrationCheck.created_at >= since)
                     .scalar() or 0)
        if ip_recent >= 20:
            block = True
            reasons.append({"code": "ip_flood", "message": f"IP {ip} 1小时内已发起 {ip_recent} 次注册"})
        elif ip_recent >= 8:
            review = True
            reasons.append({"code": "ip_burst", "message": f"IP {ip} 1小时内已发起 {ip_recent} 次注册"})

    decision = "block" if block else ("review" if review else "allow")
    coupon_allowed = decision == "allow"

    record = RegistrationCheck(
        email=email, email_domain=domain, phone=normalize_phone(phone), ip=ip,
        decision=decision, coupon_allowed=coupon_allowed, reasons=reasons,
        email_score=email_res.score, phone_score=phone_res.score,
        review_status="pending" if decision == "review" else "none",
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record
