import axios from 'axios'

const api = axios.create({ baseURL: '/api', timeout: 30000 })

// 生产环境在此注入运营后台的鉴权头
// api.interceptors.request.use(cfg => {
//   cfg.headers.Authorization = `Bearer ${localStorage.getItem('token')}`
//   return cfg
// })

export default api
