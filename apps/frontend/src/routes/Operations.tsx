import React, { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, createFinding, requestHIL, approveHIL, submitFinding } from '../lib/api'
import EvidencePanel, { EvidenceItem } from '../components/EvidencePanel'
import { toast } from '../store/toasts'

const SEVERITIES = ['critical', 'high', 'medium', 'low', 'info']

type Step = 'create' | 'evidence' | 'hil' | 'submit' | 'done'

export default function Operations() {
  const [step, setStep] = useState<Step>('create')
  const [fid, setFid] = useState('')
  const [programs, setPrograms] = useState<any[]>([])
  const [program, setProgram] = useState('')
  const [asset, setAsset] = useState('')
  const [title, setTitle] = useState('')
  const [desc, setDesc] = useState('')
  const [severity, setSeverity] = useState('medium')
  const [busy, setBusy] = useState(false)
  const [evidence, setEvidence] = useState<EvidenceItem[]>([])

  useEffect(() => {
    api.get('/programs/bbp/top50').then((r) => {
      const progs = r.data?.programs ?? r.data ?? []
      setPrograms(progs)
    }).catch(() => {})
  }, [])

  const validate = () => {
    if (!program) { toast.warning('Select a program'); return false }
    if (!asset.trim()) { toast.warning('Asset is required'); return false }
    if (title.trim().length < 10) { toast.warning('Title must be at least 10 characters'); return false }
    if (desc.trim().length < 50) { toast.warning('Description must be at least 50 characters'); return false }
    return true
  }

  const doCreate = async () => {
    if (!validate()) return
    setBusy(true)
    try {
      const r = await createFinding({ program, asset, title, description: desc, severity })
      const id = r.data?.id ?? r.data?.finding_id
      setFid(id)
      setStep('evidence')
      toast.success(`Finding created: ${id.slice(0, 8)}…`)
    } catch (e: any) {
      toast.error(`Create error: ${e.message}`)
    } finally {
      setBusy(false)
    }
  }

  const doRequestHiL = async () => {
    setBusy(true)
    try {
      await requestHIL(fid, 'Ready for HiL review')
      setStep('hil')
      toast.success('HiL review requested.')
    } catch (e: any) {
      toast.error(`HiL request error: ${e.message}`)
    } finally {
      setBusy(false)
    }
  }

  const doApprove = async () => {
    setBusy(true)
    try {
      await approveHIL(fid)
      setStep('submit')
      toast.success('HiL approved.')
    } catch (e: any) {
      toast.error(`Approve error: ${e.message}`)
    } finally {
      setBusy(false)
    }
  }

  const doSubmit = async () => {
    setBusy(true)
    try {
      const encoder = new TextEncoder()
      const buf = await crypto.subtle.digest('SHA-256', encoder.encode(fid).buffer)
      const hash = Array.from(new Uint8Array(buf)).map((b) => b.toString(16).padStart(2, '0')).join('')
      await submitFinding(fid, hash)
      setStep('done')
      toast.success('Finding submitted to program.')
    } catch (e: any) {
      toast.error(`Submit error: ${e.message}`)
    } finally {
      setBusy(false)
    }
  }

  const STEPS: Step[] = ['create', 'evidence', 'hil', 'submit', 'done']
  const stepIdx = STEPS.indexOf(step)

  return (
    <div style={{ padding: '1.5rem', fontFamily: "'JetBrains Mono', monospace", maxWidth: 800 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
        <div>
          <h1 style={{ color: '#355E3B', fontSize: '1.3rem', fontWeight: 700, margin: 0 }}>Operations</h1>
          <div style={{ color: '#6F8E7A', fontSize: '0.75rem', marginTop: 4 }}>HiL finding workflow</div>
        </div>
        <Link to='/findings/new' style={{ color: '#a78bfa', fontSize: '0.8rem', textDecoration: 'none' }}>
          Full form →
        </Link>
      </div>

      {/* Progress indicator */}
      <div style={{ display: 'flex', gap: 0, marginBottom: '1.5rem' }}>
        {['Create', 'Evidence', 'HiL', 'Submit', 'Done'].map((label, i) => (
          <div key={label} style={{ display: 'flex', alignItems: 'center', flex: 1 }}>
            <div style={{
              width: 28, height: 28, borderRadius: '50%',
              background: i < stepIdx ? '#355E3B' : i === stepIdx ? '#a78bfa' : '#355E3B',
              color: i < stepIdx ? '#000' : '#8FAF9B',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: '0.7rem', fontWeight: 700, flexShrink: 0,
            }}>{i < stepIdx ? '✓' : i + 1}</div>
            <div style={{ flex: 1, height: 2, background: i < stepIdx ? '#355E3B' : '#355E3B' }} />
            <span style={{ color: i === stepIdx ? '#a78bfa' : '#6F8E7A', fontSize: '0.65rem', marginLeft: 4, marginRight: 4 }}>{label}</span>
          </div>
        ))}
      </div>

      {/* Step: Create */}
      {step === 'create' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <FormRow label='PROGRAM'>
            {programs.length > 0 ? (
              <select value={program} onChange={(e) => setProgram(e.target.value)} style={input}>
                <option value=''>Select program…</option>
                {programs.map((p: any) => (
                  <option key={p.program_id ?? p.name} value={p.program_id ?? p.name}>
                    {p.name ?? p.program_id}
                  </option>
                ))}
              </select>
            ) : (
              <input value={program} onChange={(e) => setProgram(e.target.value)} placeholder='e.g. google_vrp' style={input} />
            )}
          </FormRow>
          <FormRow label='ASSET'>
            <input value={asset} onChange={(e) => setAsset(e.target.value)} placeholder='e.g. accounts.google.com' style={input} />
          </FormRow>
          <FormRow label='TITLE (min 10 chars)'>
            <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder='Concise vulnerability title' style={input} />
          </FormRow>
          <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 12 }}>
            <FormRow label='DESCRIPTION (min 50 chars)'>
              <textarea value={desc} onChange={(e) => setDesc(e.target.value)} rows={4} placeholder='Steps to reproduce, impact…' style={{ ...input, resize: 'vertical' }} />
            </FormRow>
            <FormRow label='SEVERITY'>
              <select value={severity} onChange={(e) => setSeverity(e.target.value)} style={input}>
                {SEVERITIES.map((s) => <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</option>)}
              </select>
            </FormRow>
          </div>
          <div>
            <button onClick={doCreate} disabled={busy} style={btnGreen}>
              {busy ? 'Creating…' : 'Create Finding →'}
            </button>
          </div>
        </div>
      )}

      {/* Step: Evidence */}
      {step === 'evidence' && (
        <div>
          <div style={{ color: '#8FAF9B', fontSize: '0.8rem', marginBottom: '1rem' }}>
            Finding <span style={{ color: '#355E3B' }}>{fid.slice(0, 12)}…</span> created.
            Add supporting evidence then proceed.
          </div>
          <div style={{ padding: '1rem', background: '#0B0C0D', border: '1px solid #355E3B', borderRadius: 6, marginBottom: '1rem' }}>
            <EvidencePanel findingId={fid} existingEvidence={evidence} onAdded={(item) => setEvidence((p) => [...p, item])} />
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <button onClick={() => setStep('create')} style={btnSecondary}>← Back</button>
            <button onClick={doRequestHiL} disabled={busy} style={btnGreen}>
              {busy ? 'Requesting…' : 'Request HiL Review →'}
            </button>
          </div>
        </div>
      )}

      {/* Step: HiL approval */}
      {step === 'hil' && (
        <div>
          <div style={{ padding: '1rem', background: '#0B0C0D', border: '1px solid #a78bfa44', borderRadius: 6, marginBottom: '1rem', color: '#a78bfa', fontSize: '0.85rem' }}>
            HiL review pending for finding {fid.slice(0, 12)}…
            <br />
            In production, a reviewer approves this in the <Link to='/operations/approvals' style={{ color: '#355E3B' }}>Approvals Dashboard</Link>.
            <br />
            Click below to approve directly (admin action).
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <button onClick={() => setStep('evidence')} style={btnSecondary}>← Back</button>
            <button onClick={doApprove} disabled={busy} style={btnGreen}>
              {busy ? 'Approving…' : 'Approve HiL →'}
            </button>
          </div>
        </div>
      )}

      {/* Step: Submit */}
      {step === 'submit' && (
        <div>
          <div style={{ color: '#8FAF9B', fontSize: '0.8rem', marginBottom: '1rem' }}>
            HiL approved. Ready to submit finding to the program.
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <button onClick={() => setStep('hil')} style={btnSecondary}>← Back</button>
            <button onClick={doSubmit} disabled={busy} style={btnGreen}>
              {busy ? 'Submitting…' : 'Submit to Program →'}
            </button>
          </div>
        </div>
      )}

      {/* Step: Done */}
      {step === 'done' && (
        <div style={{ textAlign: 'center', padding: '2rem' }}>
          <div style={{ color: '#355E3B', fontSize: '2rem', marginBottom: 12 }}>✓</div>
          <div style={{ color: '#8FAF9B', fontSize: '0.9rem', marginBottom: 16 }}>
            Finding {fid.slice(0, 12)}… submitted successfully.
          </div>
          <div style={{ display: 'flex', gap: 8, justifyContent: 'center' }}>
            <Link to={`/findings/${fid}`} style={{ ...btnGreen as any, textDecoration: 'none' }}>View Finding</Link>
            <button onClick={() => { setStep('create'); setFid(''); setTitle(''); setDesc(''); setAsset(''); setProgram(''); setEvidence([]) }} style={btnSecondary}>
              New Finding
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

function FormRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      <label style={{ color: '#6F8E7A', fontSize: '0.7rem', letterSpacing: '0.1em' }}>{label}</label>
      {children}
    </div>
  )
}

const input: React.CSSProperties = {
  width: '100%', boxSizing: 'border-box',
  padding: '0.55rem 0.75rem',
  background: '#0B0C0D',
  border: '1px solid #355E3B',
  borderRadius: 4,
  color: '#8FAF9B',
  fontFamily: 'inherit',
  fontSize: '0.85rem',
}

const btnGreen: React.CSSProperties = {
  padding: '0.55rem 1.25rem',
  background: '#355E3B',
  color: '#000',
  border: 'none',
  borderRadius: 4,
  fontFamily: 'inherit',
  fontWeight: 700,
  fontSize: '0.85rem',
  cursor: 'pointer',
  letterSpacing: '0.05em',
}

const btnSecondary: React.CSSProperties = {
  padding: '0.55rem 1rem',
  background: 'transparent',
  border: '1px solid #355E3B',
  borderRadius: 4,
  color: '#8FAF9B',
  fontFamily: 'inherit',
  fontSize: '0.85rem',
  cursor: 'pointer',
}
