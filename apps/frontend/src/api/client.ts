
import axios from 'axios'

const api = axios.create({
  baseURL: '/',
  withCredentials: true,
})

export default api
export const apiClient = api
