from datetime import datetime

from sqlalchemy import (JSON, Boolean, Column, DateTime, Integer, String,
                        Text)
from sqlalchemy.sql import func

from .database import Base


class EmailDomain(Base):
    """一次性/高风险邮箱域名名单"""
    __tablename__ = "email_domains"

    id = Column(Integer, primary_key=True)
    domain = Column(String(255), unique=True, index=True, nullable=False)
    # disposable=一次性邮箱; suspicious=高风险但非典型一次性
    category = Column(String(32), default="disposable", nullable=False)
    # manual=人工录入 public-list=公开名单同步 discovery=自动发现确认
    source = Column(String(32), default="manual", nullable=False)
    enabled = Column(Boolean, default=True, nullable=False)
    note = Column(String(500), default="")
    created_at = Column(DateTime, default=datetime.utcnow)


class PhonePrefix(Base):
    """手机号段名单:虚拟运营商/接码平台/物联网号段"""
    __tablename__ = "phone_prefixes"

    id = Column(Integer, primary_key=True)
    prefix = Column(String(32), unique=True, index=True, nullable=False)
    # virtual_carrier=虚拟运营商 sms_platform=接码平台 iot=物联网
    kind = Column(String(32), default="virtual_carrier", nullable=False)
    label = Column(String(128), default="")
    enabled = Column(Boolean, default=True, nullable=False)
    note = Column(String(500), default="")
    created_at = Column(DateTime, default=datetime.utcnow)


class RegistrationCheck(Base):
    """每一次注册检测的流水,也是行为分析和统计的数据源"""
    __tablename__ = "registration_checks"

    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    email = Column(String(255), default="")
    email_domain = Column(String(255), default="", index=True)
    phone = Column(String(32), default="")
    ip = Column(String(64), default="", index=True)
    # allow / review / block
    decision = Column(String(16), nullable=False, index=True)
    coupon_allowed = Column(Boolean, default=True, nullable=False)
    reasons = Column(JSON, default=list)
    email_score = Column(Integer, default=0)
    phone_score = Column(Integer, default=0)
    # 人工审核状态: none / pending / approved / rejected
    review_status = Column(String(16), default="none", nullable=False, index=True)
    reviewer = Column(String(64), default="")
    reviewed_at = Column(DateTime, nullable=True)
    review_note = Column(Text, default="")


class DomainCandidate(Base):
    """自动发现的疑似一次性邮箱域名,待运营确认"""
    __tablename__ = "domain_candidates"

    id = Column(Integer, primary_key=True)
    domain = Column(String(255), unique=True, index=True, nullable=False)
    # registration_burst=注册突发 disposable_mx=MX指纹 new_domain=新注册域名
    # public_list=公开名单出现 keyword=命名特征
    reason = Column(String(64), nullable=False)
    evidence = Column(JSON, default=dict)
    hits = Column(Integer, default=1)          # 累计触发次数
    reg_count_24h = Column(Integer, default=0)  # 近24h该域注册数
    # pending / confirmed / rejected
    status = Column(String(16), default="pending", nullable=False, index=True)
    source = Column(String(64), default="auto")
    first_seen = Column(DateTime, default=datetime.utcnow)
    last_seen = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
