<template>
  <div>
    <h2 class="page-title">名单管理</h2>
    <div class="tabs">
      <button :class="{ active: tab === 'email' }" @click="tab = 'email'">邮箱域名名单</button>
      <button :class="{ active: tab === 'phone' }" @click="tab = 'phone'">手机号段名单</button>
    </div>

    <!-- 邮箱域名 -->
    <div v-if="tab === 'email'" class="panel">
      <div class="toolbar">
        <input v-model="emailQuery" placeholder="搜索域名" @keyup.enter="loadDomains(1)" />
        <button class="primary" @click="loadDomains(1)">搜索</button>
        <span style="flex:1"></span>
        <input v-model="newDomain" placeholder="新增域名,如 tempmail.xyz" style="width:220px" />
        <select v-model="newCategory">
          <option value="disposable">一次性邮箱</option>
          <option value="suspicious">高风险</option>
        </select>
        <button class="primary" @click="addDomain">添加</button>
      </div>
      <table>
        <thead><tr><th>域名</th><th>分类</th><th>来源</th><th>状态</th><th>备注</th><th>操作</th></tr></thead>
        <tbody>
          <tr v-for="d in domains" :key="d.id">
            <td>{{ d.domain }}</td>
            <td><span class="tag info">{{ d.category === 'disposable' ? '一次性邮箱' : '高风险' }}</span></td>
            <td>{{ sourceText(d.source) }}</td>
            <td><span class="tag" :class="d.enabled ? 'allow' : 'rejected'">{{ d.enabled ? '启用' : '停用' }}</span></td>
            <td class="muted">{{ d.note }}</td>
            <td>
              <button @click="toggleDomain(d)">{{ d.enabled ? '停用' : '启用' }}</button>
              <button class="danger" @click="removeDomain(d)">删除</button>
            </td>
          </tr>
        </tbody>
      </table>
      <div class="pager">
        <button :disabled="emailPage <= 1" @click="loadDomains(emailPage - 1)">上一页</button>
        <span class="muted">第 {{ emailPage }} 页 / 共 {{ emailTotal }} 条</span>
        <button :disabled="emailPage * 20 >= emailTotal" @click="loadDomains(emailPage + 1)">下一页</button>
      </div>
    </div>

    <!-- 手机号段 -->
    <div v-else class="panel">
      <div class="toolbar">
        <input v-model="newPrefix" placeholder="号段,如 170 / 16501" style="width:160px" />
        <select v-model="newKind">
          <option value="virtual_carrier">虚拟运营商</option>
          <option value="sms_platform">接码平台</option>
          <option value="iot">物联网</option>
        </select>
        <input v-model="newLabel" placeholder="说明,如 某接码平台" style="width:180px" />
        <button class="primary" @click="addPrefix">添加</button>
      </div>
      <table>
        <thead><tr><th>号段</th><th>类型</th><th>说明</th><th>状态</th><th>操作</th></tr></thead>
        <tbody>
          <tr v-for="p in prefixes" :key="p.id">
            <td>{{ p.prefix }}</td>
            <td><span class="tag" :class="p.kind === 'sms_platform' ? 'block' : 'review'">{{ kindText(p.kind) }}</span></td>
            <td>{{ p.label }}</td>
            <td><span class="tag" :class="p.enabled ? 'allow' : 'rejected'">{{ p.enabled ? '启用' : '停用' }}</span></td>
            <td>
              <button @click="togglePrefix(p)">{{ p.enabled ? '停用' : '启用' }}</button>
              <button class="danger" @click="removePrefix(p)">删除</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref, watch } from 'vue'
import api from '../api'

const tab = ref('email')
const domains = ref([]), prefixes = ref([])
const emailQuery = ref(''), emailPage = ref(1), emailTotal = ref(0)
const newDomain = ref(''), newCategory = ref('disposable')
const newPrefix = ref(''), newKind = ref('virtual_carrier'), newLabel = ref('')

const sourceText = (s) => ({ manual: '人工录入', 'public-list': '公开名单', discovery: '自动发现' }[s] || s)
const kindText = (k) => ({ virtual_carrier: '虚拟运营商', sms_platform: '接码平台', iot: '物联网' }[k] || k)

async function loadDomains(page = 1) {
  emailPage.value = page
  const { data } = await api.get('/admin/email-domains', { params: { q: emailQuery.value, page, size: 20 } })
  domains.value = data.items
  emailTotal.value = data.total
}
async function addDomain() {
  if (!newDomain.value.trim()) return
  try {
    await api.post('/admin/email-domains', { domain: newDomain.value.trim(), category: newCategory.value })
    newDomain.value = ''
    loadDomains(1)
  } catch (e) { alert(e.response?.data?.detail || '添加失败') }
}
async function toggleDomain(d) {
  await api.patch(`/admin/email-domains/${d.id}`, { enabled: !d.enabled })
  loadDomains(emailPage.value)
}
async function removeDomain(d) {
  if (!confirm(`确认删除 ${d.domain}?`)) return
  await api.delete(`/admin/email-domains/${d.id}`)
  loadDomains(emailPage.value)
}

async function loadPrefixes() {
  const { data } = await api.get('/admin/phone-prefixes')
  prefixes.value = data.items
}
async function addPrefix() {
  if (!newPrefix.value.trim()) return
  try {
    await api.post('/admin/phone-prefixes', { prefix: newPrefix.value.trim(), kind: newKind.value, label: newLabel.value })
    newPrefix.value = ''; newLabel.value = ''
    loadPrefixes()
  } catch (e) { alert(e.response?.data?.detail || '添加失败') }
}
async function togglePrefix(p) {
  await api.patch(`/admin/phone-prefixes/${p.id}`, { enabled: !p.enabled })
  loadPrefixes()
}
async function removePrefix(p) {
  if (!confirm(`确认删除号段 ${p.prefix}?`)) return
  await api.delete(`/admin/phone-prefixes/${p.id}`)
  loadPrefixes()
}

watch(tab, () => { tab.value === 'email' ? loadDomains(1) : loadPrefixes() })
onMounted(() => loadDomains(1))
</script>
