import { createRouter, createWebHistory } from 'vue-router'
import Dashboard from './views/Dashboard.vue'
import Lists from './views/Lists.vue'
import Review from './views/Review.vue'
import Discovery from './views/Discovery.vue'

export default createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/dashboard' },
    { path: '/dashboard', component: Dashboard, meta: { title: '拦截概览' } },
    { path: '/lists', component: Lists, meta: { title: '名单管理' } },
    { path: '/review', component: Review, meta: { title: '人工审核' } },
    { path: '/discovery', component: Discovery, meta: { title: '新域名发现' } },
  ]
})
