
import axios from 'axios'
import { useAuth } from '../store/system'

const api = axios.create({ baseURL: '/'} )

api.interceptors.request.use((config)=>{
  const token = useAuth.getState().token
  if(token){ config.headers = config.headers || {}; config.headers['Authorization'] = `Bearer ${token}` }
  return config
})

export default api
