# 注册临时身份识别服务

针对「一次性邮箱 + 接码平台虚拟号码批量注册薅新人券」的风控服务:
注册环节实时识别临时身份,命中的注册转人工审核或限制领券,并提供新一次性域名的自动发现机制与运营后台。

## 架构

```
注册请求 ──> POST /api/check/registration ──> 检测引擎(detector.py)
                                                ├─ 邮箱: 名单匹配(含父域) + 启发式评分 + 行为信号
                                                ├─ 手机: 虚拟运营商/接码平台/物联网号段匹配
                                                └─ 组合策略 + 同IP频次
                                                      │
              ┌───────────────┬───────────────────────┤
           allow           review                   block
          正常发券      挂起转人工审核,禁券          直接拒绝
                            │
                     运营后台人工处理
                     放行→补券 / 拒绝→保持禁券
```

- **backend/**: FastAPI + SQLAlchemy(SQLite,可换 MySQL/Postgres)
- **frontend/**: Vue3 + Vite + ECharts 运营后台

## 快速开始

```bash
# 后端(端口 8000)
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --port 8000

# 前端(端口 5173,已配置 /api 代理)
cd frontend
npm install
npm run dev
```

打开 http://localhost:5173 进入运营后台;API 文档见 http://localhost:8000/docs。

## 业务侧接入

```bash
curl -X POST http://localhost:8000/api/check/registration \
  -H 'Content-Type: application/json' \
  -d '{"email":"a@mailinator.com","phone":"17012345678","ip":"1.2.3.4"}'
```

返回 `decision` 与 `coupon_allowed`:

| decision | 含义 | 业务动作 |
|---|---|---|
| `allow` | 放行 | 正常注册并发券 |
| `review` | 转人工审核 | 注册挂起,**不发券**,审核放行后补券 |
| `block` | 拦截 | 直接拒绝注册 |

## 判定策略(detector.py `POLICY` 可调)

- 命中一次性邮箱名单 → review + 禁券
- 邮箱启发式评分 ≥ 60(特征词/高危TLD/随机域名/命名模式/域名注册突发)→ review + 禁券
- 虚拟运营商、物联网号段 → review + 禁券
- 接码平台号段 → block
- 邮箱+手机双命中 → block
- 同 IP 1小时 ≥8 次注册 → review;≥20 次 → block

## 一次性邮箱新域名怎么发现(discovery.py)

四路互补,候选进队列、运营确认后一键落入正式名单:

1. **公开名单同步** — 定时拉取 GitHub 社区维护的一次性域名名单
   (disposable-email-domains、fakefilter),diff 入库;
2. **行为突发检测** — 分析自身注册流水:未知名域名 24h 内注册量突增
   (默认 ≥5 次)即进候选,这是发现「还没进任何名单的新域名」的核心手段;
3. **DNS 指纹探测** — 对候选域名查 MX 记录,指向已知一次性邮箱服务商
   基础设施的提权;同时用 RDAP 查域名注册时间,新注册域名加权;
4. **命名特征扫描** — 注册流水里出现含 temp/tmp/trash 等特征词的新域名直接进候选。

生产环境用 cron / celery beat 每天跑 `POST /api/admin/discovery/run` 即可。

## 运营后台功能

- **拦截概览**: 今日放行/审核/拦截/限券数,近30天处置趋势图,被拦最多域名、命中原因分布
- **名单管理**: 邮箱域名与手机号段的增删、启停、搜索
- **人工审核**: 待审核注册队列,放行(补券)/拒绝
- **新域名发现**: 手动触发发现流程,候选确认入名单/排除

## 生产化待办

- 后台加鉴权(JWT/SSO),`api.js` 中已留拦截器位置
- SQLite 换 MySQL/Postgres;名单加 Redis 缓存(检测接口 QPS 高时)
- 检测接口加签防刷;发现流程接定时任务
- 接码平台号段可对接第三方号码风险数据源持续补充
