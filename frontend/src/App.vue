<template>
  <div class="layout">
    <nav class="sidebar">
      <div class="logo">注册风控后台</div>
      <router-link to="/dashboard">拦截概览</router-link>
      <router-link to="/lists">名单管理</router-link>
      <router-link to="/review">人工审核</router-link>
      <router-link to="/discovery">新域名发现</router-link>
    </nav>
    <main class="main">
      <router-view />
    </main>
  </div>
</template>

<style>
.sidebar a.router-link-active { color: #fff; background: #1890ff; }
</style>
