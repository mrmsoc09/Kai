/**
 * AI ENGINE — Kaison Composer command center + LLM provider configuration.
 * This page lets operators select an LLM provider, enter API keys, pick a model,
 * and interact with Kaison Composer via the chat interface.
 *
 * Tabs: CHAT | LLM CONFIG | MCP TOOLS | AGENT STATUS
 */
import React, { useEffect, useRef, useState } from 'react'
import { getLLMConfig, saveLLMConfig, getLLMProviders } from '../lib/api'

// ─── Design tokens ────────────────────────────────────────────────────────────

const C = {
  bg: '#0B0C0D',
  card: '#111316',
  border: '#4E7A57',
  borderDim: '#2E4A38',
  green: '#355E3B',
  greenDim: '#2D4E33',
  greenGlow: 'rgba(53,94,59,0.22)',
  orange: '#D97706',
  red: '#A12B2B',
  purple: '#5A2E8A',
  text: '#8FAF9B',
  textSub: '#5F7665',
  textMute: '#6F8E7A',
  textDead: '#3A4F43',
}

const MONO = "'JetBrains Mono','Fira Code','Courier New',monospace"

// ─── Shared sub-components ────────────────────────────────────────────────────

function TabBar({
  tabs, active, onChange,
}: { tabs: { id: string; label: string; badge?: string | number }[]; active: string; onChange: (id: string) => void }) {
  return (
    <div style={{
      display: 'flex', gap: 2, borderBottom: `1px solid ${C.border}`,
      padding: '0 1.5rem', background: C.card,
    }}>
      {tabs.map(t => (
        <button
          key={t.id}
          onClick={() => onChange(t.id)}
          style={{
            padding: '10px 14px', background: 'transparent',
            border: 'none', borderBottom: `2px solid ${active === t.id ? C.green : 'transparent'}`,
            color: active === t.id ? C.green : C.textMute,
            fontFamily: MONO, fontSize: '0.65rem', fontWeight: 700,
            letterSpacing: '0.12em', cursor: 'pointer', transition: 'all 0.12s',
            display: 'flex', alignItems: 'center', gap: 6,
          }}
        >
          {t.label}
          {t.badge !== undefined && (
            <span style={{
              background: active === t.id ? C.greenGlow : 'rgba(148,163,184,0.08)',
              color: active === t.id ? C.green : C.textMute,
              border: `1px solid ${active === t.id ? 'rgba(53,94,59,0.3)' : C.border}`,
              borderRadius: 10, padding: '0 5px', fontSize: '0.58rem', fontWeight: 700,
            }}>
              {t.badge}
            </span>
          )}
        </button>
      ))}
    </div>
  )
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div style={{
      color: C.textMute, fontSize: '0.58rem', fontWeight: 700,
      letterSpacing: '0.16em', textTransform: 'uppercase',
      marginBottom: 10, marginTop: 20,
      display: 'flex', alignItems: 'center', gap: 8,
    }}>
      <div style={{ flex: 1, height: 1, background: C.border }} />
      {children}
      <div style={{ flex: 1, height: 1, background: C.border }} />
    </div>
  )
}

function InputField({
  label, value, onChange, type = 'text', placeholder = '', disabled = false,
}: {
  label: string; value: string; onChange: (v: string) => void;
  type?: string; placeholder?: string; disabled?: boolean
}) {
  const [focused, setFocused] = useState(false)
  return (
    <div style={{ marginBottom: 14 }}>
      <label style={{ display: 'block', color: C.textMute, fontSize: '0.6rem', fontWeight: 700, letterSpacing: '0.12em', marginBottom: 5 }}>
        {label}
      </label>
      <input
        type={type}
        value={value}
        onChange={e => onChange(e.target.value)}
        placeholder={placeholder}
        disabled={disabled}
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
        style={{
          width: '100%', boxSizing: 'border-box',
          background: C.bg, border: `1px solid ${focused ? C.green : C.border}`,
          borderRadius: 4, color: C.text, padding: '8px 12px',
          fontFamily: MONO, fontSize: '0.78rem', outline: 'none',
          transition: 'border-color 0.12s',
          boxShadow: focused ? `0 0 0 2px ${C.greenGlow}` : 'none',
          opacity: disabled ? 0.5 : 1,
        }}
      />
    </div>
  )
}

// ─── TAB 1: LLM Configuration ─────────────────────────────────────────────────

const PROVIDERS: Record<string, {
  label: string; color: string; requiresKey: boolean;
  models: { id: string; label: string }[]
}> = {
  anthropic: {
    label: 'Anthropic Claude', color: '#D97706', requiresKey: true,
    models: [
      { id: 'claude-opus-4-6',          label: 'Claude Opus 4.6  — Most Capable' },
      { id: 'claude-sonnet-4-6',         label: 'Claude Sonnet 4.6  — Balanced ★' },
      { id: 'claude-haiku-4-5-20251001', label: 'Claude Haiku 4.5  — Fastest' },
    ],
  },
  openai: {
    label: 'OpenAI', color: '#355E3B', requiresKey: true,
    models: [
      { id: 'gpt-4o',       label: 'GPT-4o  — Best Quality' },
      { id: 'gpt-4o-mini',  label: 'GPT-4o Mini  — Fast & Cheap' },
      { id: 'gpt-4-turbo',  label: 'GPT-4 Turbo' },
      { id: 'gpt-3.5-turbo',label: 'GPT-3.5 Turbo  — Economy' },
    ],
  },
  ollama: {
    label: 'Ollama (Local)', color: '#5A2E8A', requiresKey: false,
    models: [
      { id: 'llama3.2',       label: 'Llama 3.2' },
      { id: 'mistral',        label: 'Mistral' },
      { id: 'codellama',      label: 'CodeLlama' },
      { id: 'deepseek-coder', label: 'DeepSeek Coder' },
    ],
  },
  custom: {
    label: 'Custom / OpenAI-compatible', color: '#D97706', requiresKey: true,
    models: [],
  },
}

function LLMConfig() {
  const [provider, setProvider] = useState('')
  const [model, setModel] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [baseUrl, setBaseUrl] = useState('')
  const [temperature, setTemperature] = useState('0.3')
  const [customModel, setCustomModel] = useState('')
  const [saving, setSaving] = useState(false)
  const [status, setStatus] = useState<{ ok: boolean; msg: string } | null>(null)
  const [hasExistingKey, setHasExistingKey] = useState(false)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getLLMConfig()
      .then(r => {
        const cfg = r.data
        if (cfg.provider) setProvider(cfg.provider)
        if (cfg.model) setModel(cfg.model)
        if (cfg.base_url) setBaseUrl(cfg.base_url)
        if (cfg.temperature) setTemperature(String(cfg.temperature))
        setHasExistingKey(cfg.has_api_key)
      })
      .catch(() => {
        // Fallback to localStorage
        try {
          const raw = localStorage.getItem('kai_llm_config')
          if (raw) {
            const cfg = JSON.parse(raw)
            if (cfg.provider) setProvider(cfg.provider)
            if (cfg.model) setModel(cfg.model)
            if (cfg.base_url) setBaseUrl(cfg.base_url)
            if (cfg.api_key) setHasExistingKey(true)
          }
        } catch { /* ignore */ }
      })
      .finally(() => setLoading(false))
  }, [])

  const handleSave = async () => {
    if (!provider) { setStatus({ ok: false, msg: 'Select a provider first' }); return }
    const resolvedModel = provider === 'custom' ? customModel : model
    if (!resolvedModel) { setStatus({ ok: false, msg: 'Select or enter a model' }); return }
    if (PROVIDERS[provider]?.requiresKey && !apiKey && !hasExistingKey) {
      setStatus({ ok: false, msg: 'API key is required for this provider' }); return
    }
    setSaving(true)
    setStatus(null)
    try {
      await saveLLMConfig({
        provider, model: resolvedModel,
        api_key: apiKey,
        base_url: baseUrl,
        temperature: parseFloat(temperature) || 0.3,
      })
      // Mirror to localStorage for offline fallback
      localStorage.setItem('kai_llm_config', JSON.stringify({
        provider, model: resolvedModel,
        api_key: apiKey ? '***' : '',
        base_url: baseUrl,
      }))
      if (apiKey) setHasExistingKey(true)
      setApiKey('')  // Clear from UI after save
      setStatus({ ok: true, msg: `Saved. Kaison Composer will now use ${resolvedModel}` })
    } catch (e: any) {
      const detail = e?.response?.data?.detail
      setStatus({ ok: false, msg: typeof detail === 'string' ? detail : 'Failed to save — check backend connection' })
    } finally {
      setSaving(false)
    }
  }

  const prov = PROVIDERS[provider]

  if (loading) {
    return <div style={{ color: C.textMute, fontSize: '0.78rem', padding: '2rem' }}>Loading config…</div>
  }

  return (
    <div style={{ maxWidth: 640, padding: '1.5rem' }}>
      <div style={{ marginBottom: '1.5rem' }}>
        <div style={{ color: C.text, fontWeight: 700, fontSize: '1rem', marginBottom: 4 }}>
          LLM Provider Configuration
        </div>
        <div style={{ color: C.textMute, fontSize: '0.75rem', lineHeight: 1.55 }}>
          Kaison Composer uses the configured LLM for all reasoning, vulnerability analysis, and report generation.
          Without a valid configuration, autonomous operations will not function.
        </div>
      </div>

      {/* Provider selector */}
      <SectionLabel>SELECT PROVIDER</SectionLabel>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8, marginBottom: '1.25rem' }}>
        {Object.entries(PROVIDERS).map(([id, p]) => (
          <button
            key={id}
            onClick={() => { setProvider(id); setModel(''); }}
            style={{
              padding: '10px 8px', borderRadius: 5, cursor: 'pointer',
              background: provider === id ? `${p.color}15` : C.bg,
              border: `1px solid ${provider === id ? p.color : C.border}`,
              color: provider === id ? p.color : C.textMute,
              fontFamily: MONO, fontSize: '0.62rem', fontWeight: 700,
              letterSpacing: '0.06em', transition: 'all 0.12s',
              textAlign: 'center', lineHeight: 1.4,
            }}
          >
            <div style={{ marginBottom: 3, fontSize: '0.75rem' }}>
              {id === 'anthropic' ? '◉' : id === 'openai' ? '○' : id === 'ollama' ? '◎' : '▷'}
            </div>
            {p.label.replace(' (Local)', '')}
            {!p.requiresKey && (
              <div style={{ color: C.greenDim, fontSize: '0.5rem', marginTop: 3, letterSpacing: '0.08em' }}>
                NO KEY NEEDED
              </div>
            )}
          </button>
        ))}
      </div>

      {provider && (
        <>
          {/* Model selection */}
          <SectionLabel>SELECT MODEL</SectionLabel>
          {provider === 'custom' ? (
            <InputField
              label="Model Name (OpenAI-compatible)"
              value={customModel}
              onChange={setCustomModel}
              placeholder="e.g. my-model-v1"
            />
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: '1.25rem' }}>
              {(prov?.models ?? []).map(m => (
                <label
                  key={m.id}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 10,
                    padding: '9px 12px', borderRadius: 5, cursor: 'pointer',
                    background: model === m.id ? C.greenGlow : C.bg,
                    border: `1px solid ${model === m.id ? C.green : C.border}`,
                    transition: 'all 0.1s',
                  }}
                >
                  <input
                    type="radio"
                    name="model"
                    value={m.id}
                    checked={model === m.id}
                    onChange={() => setModel(m.id)}
                    style={{ accentColor: C.green, width: 14, height: 14 }}
                  />
                  <span style={{ color: model === m.id ? C.text : C.textSub, fontSize: '0.75rem', fontFamily: MONO }}>
                    {m.label}
                  </span>
                </label>
              ))}
            </div>
          )}

          {/* API Key */}
          {prov?.requiresKey && (
            <>
              <SectionLabel>AUTHENTICATION</SectionLabel>
              <div style={{ marginBottom: 14 }}>
                <label style={{ display: 'block', color: C.textMute, fontSize: '0.6rem', fontWeight: 700, letterSpacing: '0.12em', marginBottom: 5 }}>
                  API KEY {hasExistingKey && <span style={{ color: C.greenDim, marginLeft: 8 }}>✓ KEY STORED — LEAVE BLANK TO KEEP</span>}
                </label>
                <input
                  type="password"
                  value={apiKey}
                  onChange={e => setApiKey(e.target.value)}
                  placeholder={hasExistingKey ? '••••••••••••  (key stored — enter new to replace)' : 'Enter API key…'}
                  style={{
                    width: '100%', boxSizing: 'border-box',
                    background: C.bg, border: `1px solid ${apiKey ? C.green : C.border}`,
                    borderRadius: 4, color: C.text, padding: '8px 12px',
                    fontFamily: MONO, fontSize: '0.78rem', outline: 'none',
                    boxShadow: apiKey ? `0 0 0 2px ${C.greenGlow}` : 'none',
                  }}
                />
                <div style={{ color: C.textMute, fontSize: '0.6rem', marginTop: 5, lineHeight: 1.5 }}>
                  Key is stored server-side and never returned to the browser.
                  {provider === 'anthropic' && ' Get your key at console.anthropic.com'}
                  {provider === 'openai' && ' Get your key at platform.openai.com/api-keys'}
                </div>
              </div>
            </>
          )}

          {/* Base URL (Ollama / Custom) */}
          {(provider === 'ollama' || provider === 'custom') && (
            <InputField
              label={provider === 'ollama' ? 'Ollama Base URL' : 'API Base URL'}
              value={baseUrl}
              onChange={setBaseUrl}
              placeholder={provider === 'ollama' ? 'http://localhost:11434' : 'https://api.example.com/v1'}
            />
          )}

          {/* Temperature */}
          <SectionLabel>PARAMETERS</SectionLabel>
          <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: '1.25rem' }}>
            <div style={{ flex: 1 }}>
              <label style={{ display: 'block', color: C.textMute, fontSize: '0.6rem', fontWeight: 700, letterSpacing: '0.12em', marginBottom: 5 }}>
                TEMPERATURE: {temperature}
              </label>
              <input
                type="range" min="0" max="1.5" step="0.05"
                value={temperature}
                onChange={e => setTemperature(e.target.value)}
                style={{ width: '100%', accentColor: C.green }}
              />
              <div style={{ display: 'flex', justifyContent: 'space-between', color: C.textMute, fontSize: '0.55rem', marginTop: 3 }}>
                <span>PRECISE (0)</span><span>CREATIVE (1.5)</span>
              </div>
            </div>
          </div>

          {/* Status */}
          {status && (
            <div style={{
              padding: '10px 14px', borderRadius: 5, marginBottom: 14,
              background: status.ok ? 'rgba(53,94,59,0.08)' : 'rgba(161,43,43,0.08)',
              border: `1px solid ${status.ok ? 'rgba(53,94,59,0.35)' : 'rgba(161,43,43,0.35)'}`,
              color: status.ok ? C.green : C.red,
              fontFamily: MONO, fontSize: '0.72rem',
            }}>
              {status.ok ? '✓ ' : '✕ '}{status.msg}
            </div>
          )}

          {/* Save */}
          <button
            onClick={handleSave}
            disabled={saving}
            style={{
              padding: '10px 24px', borderRadius: 5, border: 'none',
              background: saving ? C.border : C.green,
              color: saving ? C.textMute : '#0B0C0D',
              fontFamily: MONO, fontSize: '0.72rem', fontWeight: 700,
              letterSpacing: '0.1em', cursor: saving ? 'not-allowed' : 'pointer',
              transition: 'all 0.12s',
            }}
          >
            {saving ? 'SAVING…' : 'SAVE CONFIGURATION'}
          </button>

          {/* Quick test notice */}
          <div style={{
            marginTop: 16, padding: '10px 14px', borderRadius: 5,
            background: C.bg, border: `1px solid ${C.border}`,
            color: C.textMute, fontSize: '0.65rem', lineHeight: 1.6,
          }}>
            <strong style={{ color: C.textSub }}>After saving:</strong> switch to the CHAT tab and send a test message to verify the connection.
            Configuration is applied immediately to Kaison Composer without a restart.
          </div>
        </>
      )}
    </div>
  )
}

// ─── TAB 2: Kaison Composer Chat ───────────────────────────────────────────────────

type ChatMsg = { role: 'user' | 'assistant' | 'system'; content: string; ts: string }

function AgentChat() {
  const [messages, setMessages] = useState<ChatMsg[]>([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [wsStatus, setWsStatus] = useState<'connecting' | 'open' | 'closed' | 'error'>('closed')
  const wsRef = useRef<WebSocket | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  // Check if LLM is configured
  const [llmConfigured, setLlmConfigured] = useState<boolean | null>(null)

  useEffect(() => {
    getLLMConfig()
      .then(r => setLlmConfigured(r.data.has_api_key || r.data.provider === 'ollama'))
      .catch(() => {
        const raw = localStorage.getItem('kai_llm_config')
        if (raw) {
          try { const c = JSON.parse(raw); setLlmConfigured(!!c.api_key || c.provider === 'ollama') } catch { setLlmConfigured(false) }
        } else {
          setLlmConfigured(false)
        }
      })
  }, [])

  useEffect(() => {
    if (llmConfigured === false) return
    connectWS()
    return () => { wsRef.current?.close() }
  }, [llmConfigured])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const connectWS = () => {
    setWsStatus('connecting')
    const wsProtocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const ws = new WebSocket(`${wsProtocol}://${window.location.host}/api/v1/agent-zero/ws/chat`)
    ws.onopen = () => setWsStatus('open')
    ws.onclose = () => setWsStatus('closed')
    ws.onerror = () => setWsStatus('error')
    ws.onmessage = (evt) => {
      try {
        const data = JSON.parse(evt.data)
        if (data.type === 'message' || data.content) {
          setMessages(prev => [...prev, {
            role: 'assistant',
            content: data.content || data.message || JSON.stringify(data),
            ts: new Date().toISOString(),
          }])
        } else if (data.type === 'stream_chunk') {
          setMessages(prev => {
            const last = prev[prev.length - 1]
            if (last?.role === 'assistant' && last.ts === 'streaming') {
              return [...prev.slice(0, -1), { ...last, content: last.content + (data.chunk || '') }]
            }
            return [...prev, { role: 'assistant', content: data.chunk || '', ts: 'streaming' }]
          })
        } else if (data.type === 'stream_end') {
          setMessages(prev => {
            const last = prev[prev.length - 1]
            if (last?.ts === 'streaming') {
              return [...prev.slice(0, -1), { ...last, ts: new Date().toISOString() }]
            }
            return prev
          })
          setSending(false)
        }
      } catch { /* ignore non-JSON */ }
    }
    wsRef.current = ws
  }

  const send = () => {
    if (!input.trim() || sending) return
    const msg: ChatMsg = { role: 'user', content: input.trim(), ts: new Date().toISOString() }
    setMessages(prev => [...prev, msg])
    setInput('')
    setSending(true)
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'chat', message: msg.content }))
    } else {
      connectWS()
      setMessages(prev => [...prev, {
        role: 'system',
        content: 'Connection not open. Reconnecting…',
        ts: new Date().toISOString(),
      }])
      setSending(false)
    }
  }

  const statusDot = { open: C.green, connecting: C.orange, closed: C.textMute, error: C.red }[wsStatus]
  const statusLabel = { open: 'CONNECTED', connecting: 'CONNECTING', closed: 'DISCONNECTED', error: 'ERROR' }[wsStatus]

  if (llmConfigured === false) {
    return (
      <div style={{
        display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
        height: '100%', padding: '3rem', textAlign: 'center',
      }}>
        <div style={{ color: C.orange, fontSize: '2rem', marginBottom: '1rem' }}>✦</div>
        <div style={{ color: C.text, fontWeight: 700, fontSize: '1rem', marginBottom: 8 }}>
          AI Engine Not Configured
        </div>
        <div style={{ color: C.textMute, fontSize: '0.78rem', lineHeight: 1.6, maxWidth: 400, marginBottom: '1.5rem' }}>
          Kaison Composer requires an LLM provider before it can operate. Configure your API key
          and model in the <strong style={{ color: C.orange }}>LLM CONFIG</strong> tab to enable chat and autonomous operations.
        </div>
        <div style={{
          padding: '10px 16px', borderRadius: 5, background: 'rgba(217,119,6,0.08)',
          border: `1px solid ${C.orange}`, color: C.orange,
          fontFamily: MONO, fontSize: '0.65rem', letterSpacing: '0.08em',
        }}>
          → Switch to the LLM CONFIG tab above
        </div>
      </div>
    )
  }

  const QUICK = [
    'What vulnerabilities should I prioritize?',
    'Analyze the current findings for critical issues',
    'Run recon on the active hunt scope',
    'Summarize recent scan results',
  ]

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Status bar */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 10, padding: '8px 1.5rem',
        background: C.bg, borderBottom: `1px solid ${C.border}`,
        fontSize: '0.6rem', fontFamily: MONO, letterSpacing: '0.1em',
      }}>
        <div style={{ width: 7, height: 7, borderRadius: '50%', background: statusDot, boxShadow: wsStatus === 'open' ? `0 0 6px ${C.green}` : 'none' }} />
        <span style={{ color: C.textMute }}>{statusLabel}</span>
        {wsStatus !== 'open' && (
          <button
            onClick={connectWS}
            style={{
              padding: '2px 8px', background: 'transparent', border: `1px solid ${C.border}`,
              borderRadius: 3, color: C.textMute, fontFamily: MONO, fontSize: '0.55rem',
              cursor: 'pointer', letterSpacing: '0.08em',
            }}
          >
            RECONNECT
          </button>
        )}
        <span style={{ marginLeft: 'auto', color: C.textMute }}>
          Kaison Composer · {messages.length} messages
        </span>
        <button
          onClick={() => setMessages([])}
          style={{
            padding: '2px 8px', background: 'transparent', border: `1px solid ${C.border}`,
            borderRadius: 3, color: C.textMute, fontFamily: MONO, fontSize: '0.55rem',
            cursor: 'pointer', letterSpacing: '0.08em',
          }}
        >
          CLEAR
        </button>
      </div>

      {/* Messages */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '1rem 1.5rem' }}>
        {messages.length === 0 && (
          <div style={{ textAlign: 'center', paddingTop: '3rem' }}>
            <div style={{
              fontSize: '3rem', marginBottom: '1rem',
              background: `radial-gradient(circle, ${C.purple}40, transparent)`,
              display: 'inline-block', padding: '0.5rem',
            }}>✦</div>
            <div style={{ color: C.text, fontWeight: 700, marginBottom: 8 }}>Kaison Composer</div>
            <div style={{ color: C.textMute, fontSize: '0.75rem', marginBottom: '1.5rem', lineHeight: 1.6 }}>
              AI security operations assistant · Human-in-the-Loop governed
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, justifyContent: 'center', maxWidth: 500, margin: '0 auto' }}>
              {QUICK.map((q, i) => (
                <button
                  key={i}
                  onClick={() => setInput(q)}
                  style={{
                    padding: '7px 12px', borderRadius: 4,
                    background: C.card, border: `1px solid ${C.border}`,
                    color: C.textSub, fontFamily: MONO, fontSize: '0.65rem',
                    cursor: 'pointer', transition: 'all 0.1s', textAlign: 'left',
                  }}
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m, i) => (
          <div
            key={i}
            style={{
              display: 'flex', flexDirection: m.role === 'user' ? 'row-reverse' : 'row',
              gap: 10, marginBottom: 12,
            }}
          >
            <div style={{
              width: 28, height: 28, borderRadius: '50%', flexShrink: 0,
              background: m.role === 'user' ? 'rgba(53,94,59,0.12)' : m.role === 'system' ? 'rgba(217,119,6,0.12)' : 'rgba(90,46,138,0.12)',
              border: `1px solid ${m.role === 'user' ? 'rgba(53,94,59,0.35)' : m.role === 'system' ? 'rgba(217,119,6,0.35)' : 'rgba(90,46,138,0.35)'}`,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: '0.7rem', color: m.role === 'user' ? C.green : m.role === 'system' ? C.orange : C.purple,
            }}>
              {m.role === 'user' ? 'U' : m.role === 'system' ? '!' : '✦'}
            </div>
            <div style={{
              maxWidth: '72%',
              background: m.role === 'user' ? 'rgba(53,94,59,0.06)' : m.role === 'system' ? 'rgba(217,119,6,0.06)' : C.card,
              border: `1px solid ${m.role === 'user' ? 'rgba(53,94,59,0.2)' : m.role === 'system' ? 'rgba(217,119,6,0.2)' : C.border}`,
              borderRadius: 6, padding: '10px 14px',
            }}>
              <div style={{ color: C.text, fontSize: '0.8rem', lineHeight: 1.65, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                {m.content}
              </div>
              {m.ts !== 'streaming' && (
                <div style={{ color: C.textMute, fontSize: '0.57rem', marginTop: 5 }}>
                  {new Date(m.ts).toLocaleTimeString()}
                </div>
              )}
              {m.ts === 'streaming' && (
                <div style={{ color: C.green, fontSize: '0.57rem', marginTop: 5, animation: 'pulse 1s infinite' }}>
                  ▌ generating
                </div>
              )}
            </div>
          </div>
        ))}

        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div style={{
        padding: '12px 1.5rem', borderTop: `1px solid ${C.border}`,
        background: C.bg, display: 'flex', gap: 10,
      }}>
        <input
          ref={inputRef}
          type="text"
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() } }}
          placeholder={wsStatus === 'open' ? 'Ask Kaison Composer…' : 'Connecting to Kaison Composer…'}
          disabled={sending}
          style={{
            flex: 1, background: C.card, border: `1px solid ${C.border}`,
            borderRadius: 5, color: C.text, padding: '10px 14px',
            fontFamily: MONO, fontSize: '0.8rem', outline: 'none',
          }}
          onFocus={e => { e.currentTarget.style.borderColor = C.green }}
          onBlur={e => { e.currentTarget.style.borderColor = C.border }}
        />
        <button
          onClick={send}
          disabled={sending || !input.trim()}
          style={{
            padding: '10px 20px', borderRadius: 5, border: 'none',
            background: input.trim() && !sending ? C.green : C.border,
            color: input.trim() && !sending ? '#0B0C0D' : C.textMute,
            fontFamily: MONO, fontSize: '0.68rem', fontWeight: 700,
            letterSpacing: '0.1em', cursor: input.trim() && !sending ? 'pointer' : 'not-allowed',
            transition: 'all 0.12s',
          }}
        >
          {sending ? '▌▌▌' : 'SEND'}
        </button>
      </div>
    </div>
  )
}

// ─── TAB 3: MCP Tools status ──────────────────────────────────────────────────

function MCPTools() {
  const [tools, setTools] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [servers, setServers] = useState<any[]>(() => {
    try { return JSON.parse(localStorage.getItem('k1_mcp_servers') || '[]') } catch { return [] }
  })
  const [showAdd, setShowAdd] = useState(false)
  const [form, setForm] = useState({ name: '', url: '', token: '', description: '' })

  useEffect(() => {
    const tok = localStorage.getItem('k1_token') || localStorage.getItem('K1_DEV_TOKEN') || ''
    fetch('/api/v1/tools', { headers: { Authorization: `Bearer ${tok}` } })
      .then(r => r.json())
      .then(d => setTools(Array.isArray(d) ? d : d.tools ?? []))
      .catch(() => setTools([]))
      .finally(() => setLoading(false))
  }, [])

  const cats = tools.reduce((acc: Record<string, any[]>, t) => {
    const cat = t.category || 'Other'
    acc[cat] = acc[cat] || []
    acc[cat].push(t)
    return acc
  }, {})

  const addServer = () => {
    if (!form.name.trim() || !form.url.trim()) return
    const next = [
      {
        id: `mcp-${Date.now()}`,
        name: form.name.trim(),
        url: form.url.trim(),
        token: form.token.trim(),
        description: form.description.trim(),
      },
      ...servers,
    ]
    setServers(next)
    localStorage.setItem('k1_mcp_servers', JSON.stringify(next))
    setForm({ name: '', url: '', token: '', description: '' })
    setShowAdd(false)
  }

  const removeServer = (id: string) => {
    const next = servers.filter(s => s.id !== id)
    setServers(next)
    localStorage.setItem('k1_mcp_servers', JSON.stringify(next))
  }

  return (
    <div style={{ padding: '1.5rem' }}>
      <div style={{ marginBottom: '1rem' }}>
        <div style={{ color: C.text, fontWeight: 700, fontSize: '1rem', marginBottom: 4 }}>
          MCP Tool Registry
        </div>
        <div style={{ color: C.textMute, fontSize: '0.72rem' }}>
          {loading ? 'Loading…' : `${tools.length} tools registered across ${Object.keys(cats).length} categories`}
        </div>
      </div>

      <div style={{ marginBottom: '1.25rem', padding: '12px', background: C.card, border: `1px solid ${C.border}`, borderRadius: 6 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
          <div style={{ color: C.text, fontWeight: 700, fontSize: '0.8rem' }}>MCP Servers</div>
          <button
            onClick={() => setShowAdd(v => !v)}
            style={{ background: C.green, color: '#0B0C0D', border: `1px solid ${C.border}`, borderRadius: 4, padding: '4px 10px', fontSize: '0.65rem', fontWeight: 700, cursor: 'pointer' }}
          >
            MCP +
          </button>
        </div>

        {showAdd && (
          <div style={{ marginTop: 10, display: 'grid', gap: 8 }}>
            <input
              placeholder="Server name (e.g., Recon MCP)"
              value={form.name}
              onChange={e => setForm({ ...form, name: e.target.value })}
              style={{ background: C.bg, border: `1px solid ${C.border}`, borderRadius: 4, color: C.text, padding: '6px 10px', fontFamily: MONO, fontSize: '0.7rem' }}
            />
            <input
              placeholder="Base URL (e.g., https://mcp.yourdomain.com)"
              value={form.url}
              onChange={e => setForm({ ...form, url: e.target.value })}
              style={{ background: C.bg, border: `1px solid ${C.border}`, borderRadius: 4, color: C.text, padding: '6px 10px', fontFamily: MONO, fontSize: '0.7rem' }}
            />
            <input
              placeholder="Auth token (optional)"
              value={form.token}
              onChange={e => setForm({ ...form, token: e.target.value })}
              style={{ background: C.bg, border: `1px solid ${C.border}`, borderRadius: 4, color: C.text, padding: '6px 10px', fontFamily: MONO, fontSize: '0.7rem' }}
            />
            <textarea
              placeholder="Description (optional)"
              value={form.description}
              onChange={e => setForm({ ...form, description: e.target.value })}
              style={{ background: C.bg, border: `1px solid ${C.border}`, borderRadius: 4, color: C.text, padding: '6px 10px', fontFamily: MONO, fontSize: '0.7rem', minHeight: 70 }}
            />
            <div style={{ display: 'flex', gap: 8 }}>
              <button onClick={addServer} style={{ background: C.green, color: '#0B0C0D', border: `1px solid ${C.border}`, borderRadius: 4, padding: '6px 10px', fontSize: '0.65rem', fontWeight: 700, cursor: 'pointer' }}>Save MCP</button>
              <button onClick={() => setShowAdd(false)} style={{ background: 'transparent', color: C.text, border: `1px solid ${C.border}`, borderRadius: 4, padding: '6px 10px', fontSize: '0.65rem', fontWeight: 700, cursor: 'pointer' }}>Cancel</button>
            </div>
            <div style={{ color: C.textMute, fontSize: '0.6rem' }}>
              Stored locally in your browser. No keys are exposed in the UI.
            </div>
          </div>
        )}

        {servers.length > 0 && (
          <div style={{ marginTop: 10, display: 'grid', gap: 6 }}>
            {servers.map(s => (
              <div key={s.id} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8, padding: '6px 8px', border: `1px solid ${C.border}`, borderRadius: 4, background: C.bg }}>
                <div style={{ minWidth: 0 }}>
                  <div style={{ color: C.text, fontSize: '0.72rem', fontWeight: 700 }}>{s.name}</div>
                  <div style={{ color: C.textMute, fontSize: '0.6rem', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{s.url}</div>
                </div>
                <button onClick={() => removeServer(s.id)} style={{ background: 'transparent', color: C.textMute, border: `1px solid ${C.border}`, borderRadius: 4, padding: '2px 6px', fontSize: '0.6rem', cursor: 'pointer' }}>Remove</button>
              </div>
            ))}
          </div>
        )}
      </div>
      {Object.entries(cats).map(([cat, items]) => (
        <div key={cat} style={{ marginBottom: '1.25rem' }}>
          <div style={{
            color: C.textMute, fontSize: '0.6rem', fontWeight: 700, letterSpacing: '0.14em',
            marginBottom: 8, padding: '4px 0', borderBottom: `1px solid ${C.border}`,
          }}>
            {cat.toUpperCase()} <span style={{ color: C.textMute, opacity: 0.6 }}>({items.length})</span>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 6 }}>
            {items.map((t, i) => (
              <div
                key={i}
                style={{
                  padding: '8px 12px', borderRadius: 4, background: C.bg,
                  border: `1px solid ${C.border}`,
                }}
              >
                <div style={{ color: C.textSub, fontSize: '0.72rem', fontWeight: 600, marginBottom: 2 }}>
                  {t.name || t.id}
                </div>
                <div style={{ color: C.textMute, fontSize: '0.62rem', lineHeight: 1.4 }}>
                  {t.description ? t.description.slice(0, 80) : '—'}
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}
      {!loading && tools.length === 0 && (
        <div style={{ color: C.textMute, fontSize: '0.75rem', textAlign: 'center', padding: '3rem' }}>
          No tools loaded. Check backend tool registry.
        </div>
      )}
    </div>
  )
}

// ─── TAB 4: Agent Status ─────────────────────────────────────────────────────

function AgentStatus() {
  const [state, setState] = useState<any>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const tok = localStorage.getItem('k1_token') || localStorage.getItem('K1_DEV_TOKEN') || ''
    fetch('/state/config', { headers: { Authorization: `Bearer ${tok}` } })
      .then(r => r.json())
      .then(setState)
      .catch(() => setState(null))
      .finally(() => setLoading(false))
  }, [])

  const Row = ({ label, value, color }: { label: string; value: string; color?: string }) => (
    <div style={{
      display: 'flex', justifyContent: 'space-between', alignItems: 'center',
      padding: '8px 0', borderBottom: `1px solid ${C.borderDim}`,
    }}>
      <span style={{ color: C.textMute, fontSize: '0.68rem', letterSpacing: '0.06em' }}>{label}</span>
      <span style={{ color: color || C.textSub, fontFamily: MONO, fontSize: '0.7rem' }}>{value}</span>
    </div>
  )

  if (loading) return <div style={{ padding: '2rem', color: C.textMute, fontSize: '0.75rem' }}>Loading system state…</div>
  if (!state) return <div style={{ padding: '2rem', color: C.textMute, fontSize: '0.75rem' }}>Backend unreachable</div>

  return (
    <div style={{ padding: '1.5rem', maxWidth: 700 }}>
      <div style={{ color: C.text, fontWeight: 700, fontSize: '1rem', marginBottom: '1.25rem' }}>
        System Status
      </div>
      <div style={{ background: C.bg, border: `1px solid ${C.border}`, borderRadius: 6, padding: '0 16px', marginBottom: '1rem' }}>
        <Row label="LLM Provider" value={state.providers?.primary || '—'} />
        <Row label="HiL Gate" value={state.hil_gate_enforced ? 'ENFORCED' : 'OFF'} color={state.hil_gate_enforced ? C.green : C.orange} />
        <Row label="Scope Policy" value={state.scope_policy || '—'} />
        <Row label="Vector Backend" value={state.vector?.backend || '—'} />
        <Row label="Memory Entries" value={String(state.vector?.mem_count ?? 0)} />
      </div>
      {state.providers?.models && (
        <>
          <div style={{ color: C.textMute, fontSize: '0.6rem', fontWeight: 700, letterSpacing: '0.14em', marginBottom: 8 }}>
            PROVIDER MODELS
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 6 }}>
            {Object.entries(state.providers.models as Record<string, any>).map(([k, v]) => (
              <div
                key={k}
                style={{
                  padding: '8px 12px', borderRadius: 4,
                  background: C.bg, border: `1px solid ${v.valid ? 'rgba(53,94,59,0.35)' : C.border}`,
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ color: C.textSub, fontFamily: MONO, fontSize: '0.65rem' }}>{k}</span>
                  <span style={{
                    fontSize: '0.55rem', padding: '1px 6px', borderRadius: 3, fontWeight: 700,
                    background: v.valid ? 'rgba(53,94,59,0.2)' : 'rgba(46,59,52,0.2)',
                    color: v.valid ? C.green : C.textMute,
                  }}>{v.valid ? 'VALID' : 'INVALID'}</span>
                </div>
                <div style={{ color: C.textMute, fontSize: '0.6rem', marginTop: 3 }}>{v.name || 'unset'}</div>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  )
}

// ─── Main AIEngine page ───────────────────────────────────────────────────────

export default function AIEngine() {
  const [tab, setTab] = useState<'chat' | 'config' | 'tools' | 'status'>('chat')

  const tabs = [
    { id: 'chat',   label: 'CHAT' },
    { id: 'config', label: 'LLM CONFIG' },
    { id: 'tools',  label: 'MCP TOOLS' },
    { id: 'status', label: 'AGENT STATUS' },
  ]

  return (
    <div style={{
      background: C.bg, minHeight: '100vh', display: 'flex', flexDirection: 'column',
      fontFamily: MONO,
    }}>
      {/* Page header */}
      <div style={{
        padding: '1rem 1.5rem 0', background: C.card,
        borderBottom: `1px solid ${C.border}`,
      }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 12, marginBottom: 2 }}>
          <span style={{ color: C.purple, fontSize: '1.2rem' }}>✦</span>
          <h1 style={{ color: C.text, margin: 0, fontSize: '1.1rem', fontWeight: 700, letterSpacing: '0.05em' }}>
            AI ENGINE
          </h1>
          <span style={{ color: C.textMute, fontSize: '0.65rem', letterSpacing: '0.1em' }}>
            Kaison Composer · LLM Configuration · MCP Tools
          </span>
        </div>
        <TabBar tabs={tabs} active={tab} onChange={(id) => setTab(id as any)} />
      </div>

      {/* Tab content */}
      <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column' }}>
        {tab === 'chat'   && <AgentChat />}
        {tab === 'config' && <LLMConfig />}
        {tab === 'tools'  && <MCPTools />}
        {tab === 'status' && <AgentStatus />}
      </div>
    </div>
  )
}
