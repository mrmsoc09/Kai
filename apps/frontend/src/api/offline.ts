
import { get, set } from 'idb-keyval'

export async function cachedJson<T>(key: string, fetcher: ()=> Promise<T>): Promise<T> {
  try{
    const data = await fetcher()
    set(key, data).catch(()=>{})
    return data
  }catch(e){
    const cached = await get<T>(key)
    if(cached) return cached
    throw e
  }
}
