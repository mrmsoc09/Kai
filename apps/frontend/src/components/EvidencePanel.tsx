/**
 * EvidencePanel — drag-drop evidence upload with client-side SHA256 computation.
 */
import React, { useCallback, useRef, useState } from 'react'
import { addEvidence } from '../lib/api'
import { toast } from '../store/toasts'

export type EvidenceItem = {
  id: string
  kind: string
  uri: string
  sha256_hex: string
  meta?: Record<string, any>
}

type Props = {
  findingId: string
  existingEvidence?: EvidenceItem[]
  onAdded?: (item: EvidenceItem) => void
}

const KINDS = ['screenshot', 'request_response', 'poc_script', 'log', 'video', 'other']

async function sha256Hex(buf: ArrayBuffer): Promise<string> {
  const hashBuf = await crypto.subtle.digest('SHA-256', buf)
  return Array.from(new Uint8Array(hashBuf)).map((b) => b.toString(16).padStart(2, '0')).join('')
}

export default function EvidencePanel({ findingId, existingEvidence = [], onAdded }: Props) {
  const [uploading, setUploading] = useState(false)
  const [dragOver, setDragOver] = useState(false)
  const [kind, setKind] = useState('screenshot')
  const [uriInput, setUriInput] = useState('')
  const fileRef = useRef<HTMLInputElement>(null)

  const processFile = useCallback(async (file: File) => {
    setUploading(true)
    try {
      const buf = await file.arrayBuffer()
      const hash = await sha256Hex(buf)
      // Upload as base64 data URI placeholder; real implementation would upload to object storage
      const uri = `evidence://${findingId}/${encodeURIComponent(file.name)}`
      const res = await addEvidence(findingId, {
        kind,
        uri,
        sha256_hex: hash,
        meta: { filename: file.name, size: file.size, mime: file.type },
      })
      toast.success(`Evidence "${file.name}" added.`)
      onAdded?.({ id: res.data?.id ?? hash, kind, uri, sha256_hex: hash, meta: { filename: file.name } })
    } catch (e: any) {
      toast.error(`Failed to add evidence: ${e.message}`)
    } finally {
      setUploading(false)
    }
  }, [findingId, kind, onAdded])

  const processUri = useCallback(async () => {
    const uri = uriInput.trim()
    if (!uri) return
    // Basic URI validation
    if (!uri.startsWith('http://') && !uri.startsWith('https://') && !uri.startsWith('file://')) {
      toast.error('URI must start with http://, https://, or file://')
      return
    }
    setUploading(true)
    try {
      const encoder = new TextEncoder()
      const hash = await sha256Hex(encoder.encode(uri).buffer)
      const res = await addEvidence(findingId, { kind, uri, sha256_hex: hash })
      toast.success('Evidence URI added.')
      onAdded?.({ id: res.data?.id ?? hash, kind, uri, sha256_hex: hash })
      setUriInput('')
    } catch (e: any) {
      toast.error(`Failed to add evidence: ${e.message}`)
    } finally {
      setUploading(false)
    }
  }, [findingId, kind, uriInput, onAdded])

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
    const file = e.dataTransfer.files?.[0]
    if (file) processFile(file)
  }, [processFile])

  const onFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) processFile(file)
  }

  return (
    <div style={{ fontFamily: "'JetBrains Mono', monospace" }}>
      <h3 style={{ color: '#355E3B', fontSize: '0.9rem', marginBottom: '1rem' }}>Evidence</h3>

      {/* Existing evidence list */}
      {existingEvidence.length > 0 && (
        <div style={{ marginBottom: '1rem', display: 'flex', flexDirection: 'column', gap: 6 }}>
          {existingEvidence.map((ev) => (
            <div key={ev.id} style={{
              display: 'flex', gap: 10, alignItems: 'center',
              padding: '0.5rem 0.75rem',
              background: '#0B0C0D',
              border: '1px solid #355E3B',
              borderRadius: 4,
              fontSize: '0.75rem',
            }}>
              <span style={{ color: '#a78bfa', minWidth: 90 }}>{ev.kind}</span>
              <span style={{ color: '#8FAF9B', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{ev.uri}</span>
              <span style={{ color: '#355E3B', fontSize: '0.65rem', fontFamily: 'monospace' }}>
                {ev.sha256_hex.slice(0, 12)}…
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Kind selector */}
      <div style={{ display: 'flex', gap: 8, marginBottom: '0.75rem' }}>
        <label style={{ color: '#6F8E7A', fontSize: '0.7rem', alignSelf: 'center' }}>KIND</label>
        <select
          value={kind}
          onChange={(e) => setKind(e.target.value)}
          style={{
            padding: '0.35rem 0.6rem',
            background: '#0f1117',
            border: '1px solid #355E3B',
            borderRadius: 4,
            color: '#8FAF9B',
            fontFamily: 'inherit',
            fontSize: '0.8rem',
          }}
        >
          {KINDS.map((k) => <option key={k} value={k}>{k.replace('_', ' ')}</option>)}
        </select>
      </div>

      {/* Drop zone */}
      <div
        onDrop={onDrop}
        onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
        onDragLeave={() => setDragOver(false)}
        onClick={() => fileRef.current?.click()}
        style={{
          border: `2px dashed ${dragOver ? '#355E3B' : '#355E3B'}`,
          borderRadius: 6,
          padding: '2rem',
          textAlign: 'center',
          cursor: 'pointer',
          background: dragOver ? '#355E3B08' : 'transparent',
          transition: 'all 0.15s',
          marginBottom: '0.75rem',
        }}
      >
        <div style={{ color: '#6F8E7A', fontSize: '0.8rem' }}>
          {uploading ? 'Uploading…' : 'Drop file here or click to browse'}
        </div>
        <div style={{ color: '#355E3B', fontSize: '0.7rem', marginTop: 4 }}>
          SHA-256 computed client-side before upload
        </div>
        <input ref={fileRef} type='file' style={{ display: 'none' }} onChange={onFileChange} />
      </div>

      {/* URI input */}
      <div style={{ display: 'flex', gap: 8 }}>
        <input
          value={uriInput}
          onChange={(e) => setUriInput(e.target.value)}
          placeholder='Or paste a URL/URI…'
          style={{
            flex: 1,
            padding: '0.45rem 0.65rem',
            background: '#0B0C0D',
            border: '1px solid #355E3B',
            borderRadius: 4,
            color: '#8FAF9B',
            fontFamily: 'inherit',
            fontSize: '0.8rem',
          }}
          onKeyDown={(e) => e.key === 'Enter' && processUri()}
        />
        <button
          onClick={processUri}
          disabled={!uriInput.trim() || uploading}
          style={{
            padding: '0.45rem 0.9rem',
            background: '#355E3B',
            color: '#000',
            border: 'none',
            borderRadius: 4,
            fontFamily: 'inherit',
            fontWeight: 700,
            fontSize: '0.8rem',
            cursor: !uriInput.trim() || uploading ? 'not-allowed' : 'pointer',
            opacity: !uriInput.trim() || uploading ? 0.4 : 1,
          }}
        >
          Add
        </button>
      </div>
    </div>
  )
}
