<template>
  <div>
    <h2 class="page-title">人工审核队列</h2>
    <div class="tabs">
      <button :class="{ active: status === 'pending' }" @click="switchStatus('pending')">待审核</button>
      <button :class="{ active: status === 'approved' }" @click="switchStatus('approved')">已放行</button>
      <button :class="{ active: status === 'rejected' }" @click="switchStatus('rejected')">已拒绝</button>
    </div>

    <div class="panel">
      <table>
        <thead>
          <tr><th>时间</th><th>邮箱</th><th>手机号</th><th>IP</th><th>命中原因</th><th>状态</th><th v-if="status === 'pending'">操作</th></tr>
        </thead>
        <tbody>
          <tr v-for="c in items" :key="c.id">
            <td class="muted">{{ fmt(c.created_at) }}</td>
            <td>{{ c.email }}</td>
            <td>{{ c.phone || '-' }}</td>
            <td>{{ c.ip || '-' }}</td>
            <td>
              <div v-for="(r, i) in c.reasons" :key="i" class="muted">{{ r.message }}</div>
            </td>
            <td><span class="tag" :class="c.review_status">{{ statusText(c.review_status) }}</span></td>
            <td v-if="status === 'pending'">
              <button class="success" @click="resolve(c, 'approve')">放行并补券</button>
              <button class="danger" @click="resolve(c, 'reject')">拒绝</button>
            </td>
          </tr>
          <tr v-if="!items.length"><td colspan="7" class="muted">暂无记录</td></tr>
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

const statusText = (s) => ({ pending: '待审核', approved: '已放行', rejected: '已拒绝' }[s] || s)
const fmt = (iso) => iso ? iso.replace('T', ' ').slice(0, 19) : ''

async function load(p = 1) {
  page.value = p
  const { data } = await api.get('/admin/reviews', { params: { status: status.value, page: p, size: 20 } })
  items.value = data.items
  total.value = data.total
}
function switchStatus(s) { status.value = s; load(1) }
async function resolve(c, action) {
  const msg = action === 'approve' ? '放行该注册并允许补发新人券?' : '拒绝该注册(保持禁券)?'
  if (!confirm(msg)) return
  await api.post(`/admin/reviews/${c.id}`, { action, reviewer: 'admin' })
  load(page.value)
}
onMounted(() => load(1))
</script>
