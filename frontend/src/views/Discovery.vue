<template>
  <div>
    <h2 class="page-title">新域名发现</h2>

    <div class="panel">
      <h3>发现引擎</h3>
      <div class="toolbar">
        <button class="primary" :disabled="running" @click="runFull">
          {{ running ? '运行中…' : '运行完整发现流程' }}
        </button>
        <button :disabled="running" @click="syncLists">仅同步公开名单</button>
        <button :disabled="running" @click="scanOnly">仅扫描注册行为</button>
      </div>
      <p class="muted">
        完整流程 = 同步开源一次性域名名单 → 扫描注册流水中的域名突发/命名特征 → 对待确认域名做 MX 指纹与域名年龄(RDAP)探测。
        生产环境建议配置定时任务每天自动运行。
      </p>
      <pre v-if="lastResult" class="evidence">{{ JSON.stringify(lastResult, null, 2) }}</pre>
    </div>

    <div class="tabs">
      <button :class="{ active: status === 'pending' }" @click="switchStatus('pending')">待确认</button>
      <button :class="{ active: status === 'confirmed' }" @click="switchStatus('confirmed')">已入名单</button>
      <button :class="{ active: status === 'rejected' }" @click="switchStatus('rejected')">已排除</button>
    </div>

    <div class="panel">
      <table>
        <thead>
          <tr><th>域名</th><th>发现途径</th><th>证据</th><th>强度</th><th>首次出现</th><th v-if="status === 'pending'">操作</th></tr>
        </thead>
        <tbody>
          <tr v-for="c in items" :key="c.id">
            <td>{{ c.domain }}</td>
            <td><span class="tag info">{{ reasonText(c.reason) }}</span></td>
            <td><pre class="evidence">{{ evidenceText(c.evidence) }}</pre></td>
            <td>{{ c.hits }}</td>
            <td class="muted">{{ fmt(c.first_seen) }}</td>
            <td v-if="status === 'pending'">
              <button class="danger" @click="confirm(c)">确认为一次性邮箱</button>
              <button @click="reject(c)">排除</button>
            </td>
          </tr>
          <tr v-if="!items.length"><td colspan="6" class="muted">暂无候选,可先运行上方发现流程</td></tr>
        </tbody>
      </table>
      <div class="pager">
        <button :disabled="page <= 1" @click="load(page - 1)">上一页</button>
        <span class="muted">第 {{ page }} 页 / 共 {{ total }} 条</span>
        <button :disabled="page * 20 >= total" @click="load(page + 1)">下一页</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import api from '../api'

const status = ref('pending')
const items = ref([]), page = ref(1), total = ref(0)
const running = ref(false), lastResult = ref(null)

const REASONS = {
  registration_burst: '注册行为突发',
  disposable_mx: 'MX 指纹命中',
  keyword: '命名特征',
  new_domain: '域名注册时间新',
}
const reasonText = (r) => REASONS[r] || r
const fmt = (iso) => iso ? iso.replace('T', ' ').slice(0, 19) : ''
const evidenceText = (ev) => {
  if (!ev) return ''
  const parts = []
  if (ev.regs_in_window) parts.push(`${ev.window_hours}h内注册${ev.regs_in_window}次/${ev.distinct_ips}个IP`)
  if (ev.matched_keyword) parts.push(`含特征词 ${ev.matched_keyword}`)
  if (ev.mx_fingerprint) parts.push(`MX 指向 ${ev.mx_fingerprint}`)
  if (ev.domain_age_days != null) parts.push(`域名注册 ${ev.domain_age_days} 天`)
  return parts.join(';') || JSON.stringify(ev)
}

async function load(p = 1) {
  page.value = p
  const { data } = await api.get('/admin/candidates', { params: { status: status.value, page: p, size: 20 } })
  items.value = data.items
  total.value = data.total
}
function switchStatus(s) { status.value = s; load(1) }

async function runFull() {
  running.value = true
  try { lastResult.value = (await api.post('/admin/discovery/run')).data; load(1) }
  finally { running.value = false }
}
async function syncLists() {
  running.value = true
  try { lastResult.value = (await api.post('/admin/discovery/sync-lists')).data; load(1) }
  finally { running.value = false }
}
async function scanOnly() {
  running.value = true
  try { lastResult.value = (await api.post('/admin/discovery/scan')).data; load(1) }
  finally { running.value = false }
}
async function confirm(c) {
  await api.post(`/admin/candidates/${c.id}/confirm`, { category: 'disposable' })
  load(page.value)
}
async function reject(c) {
  await api.post(`/admin/candidates/${c.id}/reject`)
  load(page.value)
}
onMounted(() => load(1))
</script>
