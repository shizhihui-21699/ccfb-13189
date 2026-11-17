from sqlalchemy.orm import Session

from .models import EmailDomain, PhonePrefix

DEFAULT_DISPOSABLE_DOMAINS = [
    "mailinator.com", "tempmail.com", "temp-mail.org", "10minutemail.com",
    "guerrillamail.com", "sharklasers.com", "yopmail.com", "getnada.com",
    "mohmal.com", "maildrop.cc", "dispostable.com", "fakeinbox.com",
    "throwawaymail.com", "tempail.com", "emailondeck.com", "mailsac.com",
    "linshiyouxiang.net", "24mail.chacuo.net", "bccto.me", "crilrem.com",
    "mailnesia.com", "spamgourmet.com", "trashmail.com", "mytrashmail.com",
    "tempinbox.com", "anonbox.net", "fakemailgenerator.com", "courrieltemporaire.com",
    "jetable.org", "discard.email", "tmpmail.org", "1secmail.com",
]

# 中国虚拟运营商/物联网号段(运营可在后台继续维护)
DEFAULT_PHONE_PREFIXES = [
    ("162", "virtual_carrier", "电信虚拟运营商"),
    ("165", "virtual_carrier", "移动虚拟运营商"),
    ("167", "virtual_carrier", "联通虚拟运营商"),
    ("170", "virtual_carrier", "虚拟运营商(小米/阿里通信等)"),
    ("171", "virtual_carrier", "联通虚拟运营商"),
    ("144", "iot", "物联网号段"),
    ("146", "iot", "物联网号段"),
    ("148", "iot", "物联网号段"),
    ("149", "iot", "物联网号段"),
    ("1740", "iot", "卫星通信号段"),
]


def seed_if_empty(db: Session) -> None:
    if db.query(EmailDomain).count() == 0:
        for d in DEFAULT_DISPOSABLE_DOMAINS:
            db.add(EmailDomain(domain=d, category="disposable",
                               source="manual", note="内置种子"))
    if db.query(PhonePrefix).count() == 0:
        for prefix, kind, label in DEFAULT_PHONE_PREFIXES:
            db.add(PhonePrefix(prefix=prefix, kind=kind, label=label,
                               note="内置种子"))
    db.commit()
