import { create } from 'zustand'

export type ToastKind = 'success' | 'error' | 'info' | 'warning'

export type Toast = {
  id: string
  kind: ToastKind
  message: string
}

type ToastStore = {
  toasts: Toast[]
  push: (kind: ToastKind, message: string) => void
  dismiss: (id: string) => void
}

let _seq = 0

export const useToasts = create<ToastStore>()((set) => ({
  toasts: [],
  push: (kind, message) => {
    const id = `t${++_seq}`
    set((s) => ({ toasts: [...s.toasts, { id, kind, message }] }))
    setTimeout(() => {
      set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) }))
    }, 4500)
  },
  dismiss: (id) => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),
}))

// Convenience helpers
export const toast = {
  success: (msg: string) => useToasts.getState().push('success', msg),
  error: (msg: string) => useToasts.getState().push('error', msg),
  info: (msg: string) => useToasts.getState().push('info', msg),
  warning: (msg: string) => useToasts.getState().push('warning', msg),
}
