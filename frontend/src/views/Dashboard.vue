<template>
  <div>
    <h2 class="page-title">拦截概览</h2>

    <div class="cards" v-if="overview">
      <div class="card"><div class="label">今日注册检测</div><div class="num">{{ overview.today.total }}</div></div>
      <div class="card"><div class="label">今日放行</div><div class="num success">{{ overview.today.allow }}</div></div>
      <div class="card"><div class="label">今日转人工审核</div><div class="num warning">{{ overview.today.review }}</div></div>
      <div class="card"><div class="label">今日拦截</div><div class="num danger">{{ overview.today.block }}</div></div>
      <div class="card"><div class="label">今日限制领券</div><div class="num danger">{{ overview.today.coupon_blocked }}</div></div>
    </div>

    <div class="cards" v-if="overview">
      <div class="card"><div class="label">邮箱域名名单(启用)</div><div class="num">{{ overview.lists.email_domains }}</div></div>
      <div class="card"><div class="label">手机号段名单(启用)</div><div class="num">{{ overview.lists.phone_prefixes }}</div></div>
      <div class="card"><div class="label">待审核注册</div><div class="num warning">{{ overview.lists.pending_reviews }}</div></div>
      <div class="card"><div class="label">待确认新域名</div><div class="num warning">{{ overview.lists.pending_candidates }}</div></div>
    </div>

    <div class="panel">
      <h3>近30天处置趋势</h3>
      <div ref="chartRef" style="height: 320px"></div>
    </div>

    <div style="display:grid; grid-template-columns: 1fr 1fr; gap:16px;">
      <div class="panel">
        <h3>近7天被拦最多的邮箱域</h3>
        <table>
          <thead><tr><th>域名</th><th>拦截/审核次数</th></tr></thead>
          <tbody>
            <tr v-for="item in topDomains" :key="item.domain">
              <td>{{ item.domain }}</td><td>{{ item.count }}</td>
            </tr>
            <tr v-if="!topDomains.length"><td colspan="2" class="muted">暂无数据</td></tr>
          </tbody>
        </table>
      </div>
      <div class="panel">
        <h3>近7天命中原因分布</h3>
        <table>
          <thead><tr><th>原因</th><th>次数</th></tr></thead>
          <tbody>
            <tr v-for="item in topReasons" :key="item.code">
              <td>{{ reasonText(item.code) }}</td><td>{{ item.count }}</td>
            </tr>
            <tr v-if="!topReasons.length"><td colspan="2" class="muted">暂无数据</td></tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import * as echarts from 'echarts'
import api from '../api'

const overview = ref(null)
const topDomains = ref([])
const topReasons = ref([])
const chartRef = ref(null)

const REASON_MAP = {
  email_blocklist: '命中一次性邮箱名单',
  email_keyword: '域名含临时邮箱特征词',
  email_risky_tld: '滥用高发顶级域',
  email_random_domain: '域名疑似随机生成',
  email_mail_pattern: '临时邮箱命名模式',
  email_domain_burst: '域名注册突发',
  phone_virtual_carrier: '虚拟运营商号段',
  phone_sms_platform: '接码平台号段',
  phone_iot: '物联网号段',
  combo_hit: '邮箱手机双命中',
  ip_burst: '同IP短时注册偏多',
  ip_flood: '同IP批量注册',
}
const reasonText = (code) => REASON_MAP[code] || code

onMounted(async () => {
  const [ov, daily, td, tr] = await Promise.all([
    api.get('/admin/stats/overview'),
    api.get('/admin/stats/daily', { params: { days: 30 } }),
    api.get('/admin/stats/top-domains'),
    api.get('/admin/stats/top-reasons'),
  ])
  overview.value = ov.data
  topDomains.value = td.data.items
  topReasons.value = tr.data.items

  const days = daily.data.days
  const chart = echarts.init(chartRef.value)
  chart.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: ['放行', '人工审核', '拦截'] },
    grid: { left: 40, right: 20, top: 40, bottom: 30 },
    xAxis: { type: 'category', data: days.map(d => d.date) },
    yAxis: { type: 'value', minInterval: 1 },
    series: [
      { name: '放行', type: 'bar', stack: 'x', itemStyle: { color: '#67c23a' }, data: days.map(d => d.allow) },
      { name: '人工审核', type: 'bar', stack: 'x', itemStyle: { color: '#e6a23c' }, data: days.map(d => d.review) },
      { name: '拦截', type: 'bar', stack: 'x', itemStyle: { color: '#f56c6c' }, data: days.map(d => d.block) },
    ],
  })
  window.addEventListener('resize', () => chart.resize())
})
</script>
