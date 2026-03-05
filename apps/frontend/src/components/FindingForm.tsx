/**
 * FindingForm — validated creation form using react-hook-form + zod.
 * Used on /findings/new and optionally for editing.
 */
import React, { useEffect, useState } from 'react'
import { useForm } from 'react-hook-form'
import { z } from 'zod'
import { zodResolver } from '@hookform/resolvers/zod'
import { api, createFinding } from '../lib/api'
import { toast } from '../store/toasts'
import { useNavigate } from 'react-router-dom'

const schema = z.object({
  program: z.string().min(1, 'Program is required'),
  asset: z.string().min(1, 'Asset is required').max(500),
  title: z.string().min(10, 'Title must be at least 10 characters').max(200),
  description: z.string().min(50, 'Description must be at least 50 characters').max(10000),
  severity: z.enum(['critical', 'high', 'medium', 'low', 'info'], {
    error: 'Select a valid severity',
  }),
  cvss_score: z.string().optional().refine(
    (v) => !v || (!isNaN(parseFloat(v)) && parseFloat(v) >= 0 && parseFloat(v) <= 10),
    { message: 'CVSS must be 0.0–10.0' }
  ),
})

type FormData = z.infer<typeof schema>

type Program = { program_id: string; name: string }

export default function FindingForm() {
  const navigate = useNavigate()
  const [programs, setPrograms] = useState<Program[]>([])
  const [submitting, setSubmitting] = useState(false)

  const {
    register,
    handleSubmit,
    formState: { errors, isValid, touchedFields },
  } = useForm<FormData>({
    resolver: zodResolver(schema),
    mode: 'onChange',
    defaultValues: { severity: 'medium' },
  })

  useEffect(() => {
    api.get('/programs/bbp/top50').then((r) => {
      setPrograms(r.data?.programs ?? r.data ?? [])
    }).catch(() => { /* silent — dropdown falls back to text */ })
  }, [])

  const onSubmit = async (data: FormData) => {
    setSubmitting(true)
    try {
      const res = await createFinding({
        program: data.program,
        asset: data.asset,
        title: data.title,
        description: data.description,
        severity: data.severity,
      })
      const fid: string = res.data?.id ?? res.data?.finding_id
      toast.success('Finding created.')
      navigate(`/findings/${fid}`)
    } catch (e: any) {
      const detail = e?.response?.data?.detail
      toast.error(typeof detail === 'string' ? detail : `Failed to create finding: ${e.message}`)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div style={{ padding: '1.5rem', maxWidth: 700, fontFamily: "'JetBrains Mono', monospace" }}>
      <h1 style={{ color: '#00FF41', fontSize: '1.3rem', fontWeight: 700, marginBottom: '1.5rem' }}>
        New Finding
      </h1>

      <form onSubmit={handleSubmit(onSubmit)} style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
        {/* Program */}
        <Field label='PROGRAM' error={errors.program?.message}>
          {programs.length > 0 ? (
            <select {...register('program')} style={inputStyle(!!errors.program)}>
              <option value=''>Select a program…</option>
              {programs.map((p: any) => (
                <option key={p.program_id ?? p.name} value={p.program_id ?? p.name}>
                  {p.name ?? p.program_id}
                </option>
              ))}
            </select>
          ) : (
            <input {...register('program')} placeholder='e.g. google_vrp' style={inputStyle(!!errors.program)} />
          )}
        </Field>

        {/* Asset */}
        <Field label='ASSET / TARGET' error={errors.asset?.message}>
          <input {...register('asset')} placeholder='e.g. accounts.example.com' style={inputStyle(!!errors.asset)} />
        </Field>

        {/* Title */}
        <Field label='TITLE' error={errors.title?.message}>
          <input {...register('title')} placeholder='Concise vulnerability title (min 10 chars)' style={inputStyle(!!errors.title)} />
          {touchedFields.title && !errors.title && (
            <span style={{ color: '#00FF41', fontSize: '0.7rem', marginTop: 4 }}>✓ Looks good</span>
          )}
        </Field>

        {/* Severity + CVSS */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
          <Field label='SEVERITY' error={errors.severity?.message}>
            <select {...register('severity')} style={inputStyle(!!errors.severity)}>
              <option value='critical'>Critical</option>
              <option value='high'>High</option>
              <option value='medium'>Medium</option>
              <option value='low'>Low</option>
              <option value='info'>Info</option>
            </select>
          </Field>
          <Field label='CVSS SCORE (optional)' error={errors.cvss_score?.message}>
            <input
              {...register('cvss_score')}
              placeholder='0.0–10.0'
              style={inputStyle(!!errors.cvss_score)}
              type='number'
              step='0.1'
              min='0'
              max='10'
            />
          </Field>
        </div>

        {/* Description */}
        <Field label='DESCRIPTION' error={errors.description?.message}>
          <textarea
            {...register('description')}
            placeholder='Describe the vulnerability, steps to reproduce, and impact. Minimum 50 characters.'
            rows={8}
            style={{ ...inputStyle(!!errors.description), resize: 'vertical' }}
          />
        </Field>

        {/* Submit */}
        <div style={{ display: 'flex', gap: 12, justifyContent: 'flex-end' }}>
          <button
            type='button'
            onClick={() => navigate('/findings')}
            style={{
              padding: '0.6rem 1.25rem',
              background: 'transparent',
              border: '1px solid #1e2330',
              color: '#8892a4',
              borderRadius: 4,
              fontFamily: 'inherit',
              fontSize: '0.85rem',
              cursor: 'pointer',
            }}
          >
            Cancel
          </button>
          <button
            type='submit'
            disabled={!isValid || submitting}
            style={{
              padding: '0.6rem 1.5rem',
              background: !isValid || submitting ? '#1a2e1a' : '#00FF41',
              color: !isValid || submitting ? '#4a5568' : '#000',
              border: 'none',
              borderRadius: 4,
              fontFamily: 'inherit',
              fontWeight: 700,
              fontSize: '0.85rem',
              cursor: !isValid || submitting ? 'not-allowed' : 'pointer',
              letterSpacing: '0.05em',
            }}
          >
            {submitting ? 'CREATING…' : 'CREATE FINDING'}
          </button>
        </div>
      </form>
    </div>
  )
}

function Field({ label, error, children }: { label: string; error?: string; children: React.ReactNode }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      <label style={{ color: '#8892a4', fontSize: '0.7rem', letterSpacing: '0.1em' }}>{label}</label>
      {children}
      {error && <span style={{ color: '#f97316', fontSize: '0.72rem' }}>{error}</span>}
    </div>
  )
}

const inputStyle = (hasError: boolean): React.CSSProperties => ({
  width: '100%',
  boxSizing: 'border-box',
  padding: '0.55rem 0.75rem',
  background: '#070809',
  border: `1px solid ${hasError ? '#f97316' : '#1e2330'}`,
  borderRadius: 4,
  color: '#e2e8f0',
  fontFamily: 'inherit',
  fontSize: '0.85rem',
  outline: 'none',
})
