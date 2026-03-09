import React, { useEffect, useState } from 'react';
import KeyManagement from '../components/KeyManagement';
import { COLORS } from '@/theme/branding';

export default function Settings(){
  const [api, setApi] = useState('');
  const [tok, setTok] = useState('');
  const [logoData, setLogoData] = useState<string>(() => localStorage.getItem('k1_logo_dataurl') || '');
  const [iconData, setIconData] = useState<string>(() => localStorage.getItem('k1_icon_dataurl') || '');
  const [brandError, setBrandError] = useState<string>('');
  useEffect(()=>{ setApi(localStorage.getItem('api_base')||''); setTok(localStorage.getItem('k1_token')||localStorage.getItem('K1_DEV_TOKEN')||''); },[]);
  const save = ()=>{
    if(api) localStorage.setItem('api_base', api);
    if(tok) { localStorage.setItem('k1_token', tok); localStorage.setItem('K1_DEV_TOKEN', tok); }
    alert('Saved. Refresh the app to apply API base env if needed.');
  };
  const panelStyle: React.CSSProperties = {
    background: COLORS.surface,
    border: `2px solid ${COLORS.border}`,
    borderRadius: 10,
    padding: '16px',
  }

  const labelStyle: React.CSSProperties = {
    display: 'block',
    color: COLORS.textSecondary,
    fontSize: '0.75rem',
    marginBottom: 6,
    letterSpacing: '0.08em',
    fontWeight: 700,
  }

  const inputStyle: React.CSSProperties = {
    width: '100%',
    background: COLORS.background,
    border: `1px solid ${COLORS.border}`,
    borderRadius: 6,
    padding: '8px 10px',
    color: COLORS.text,
    fontFamily: "'JetBrains Mono','Fira Code',monospace",
    fontSize: '0.75rem',
  }

  const stripWhiteBackground = (dataUrl: string): Promise<string> => new Promise((resolve) => {
    const img = new Image()
    img.onload = () => {
      try {
        const canvas = document.createElement('canvas')
        canvas.width = img.width
        canvas.height = img.height
        const ctx = canvas.getContext('2d')
        if (!ctx) return resolve(dataUrl)
        ctx.drawImage(img, 0, 0)
        const imgData = ctx.getImageData(0, 0, canvas.width, canvas.height)
        const d = imgData.data
        for (let i = 0; i < d.length; i += 4) {
          const r = d[i], g = d[i + 1], b = d[i + 2]
          if (r > 245 && g > 245 && b > 245) {
            d[i + 3] = 0
          }
        }
        ctx.putImageData(imgData, 0, 0)
        resolve(canvas.toDataURL('image/png'))
      } catch {
        resolve(dataUrl)
      }
    }
    img.onerror = () => resolve(dataUrl)
    img.src = dataUrl
  })

  const applyAsset = async (
    data: string,
    storageKey: 'k1_logo_dataurl' | 'k1_icon_dataurl',
    setter: (v: string) => void,
    cleanFlagKey: 'k1_logo_cleaned' | 'k1_icon_cleaned'
  ) => {
    try {
      const cleaned = await stripWhiteBackground(data)
      localStorage.setItem(storageKey, cleaned)
      localStorage.setItem(cleanFlagKey, '1')
      setter(cleaned)
      const link = document.querySelector<HTMLLinkElement>('#app-favicon')
      if (storageKey === 'k1_icon_dataurl' && link) link.href = cleaned
      window.dispatchEvent(new Event('k1-branding'))
    } catch (e: any) {
      setBrandError('Branding import failed. Try a smaller PNG/JPG image.')
    }
  }

  const handleAssetUpload = (file: File, storageKey: 'k1_logo_dataurl' | 'k1_icon_dataurl', setter: (v: string) => void, cleanFlagKey: 'k1_logo_cleaned' | 'k1_icon_cleaned') => {
    setBrandError('')
    if (file.size > 5 * 1024 * 1024) {
      setBrandError('Image too large. Max 5MB recommended.')
      return
    }
    const reader = new FileReader()
    reader.onload = async () => {
      const data = String(reader.result || '')
      await applyAsset(data, storageKey, setter, cleanFlagKey)
    }
    reader.readAsDataURL(file)
  }

  const clearAsset = (storageKey: 'k1_logo_dataurl' | 'k1_icon_dataurl', setter: (v: string) => void, cleanFlagKey: 'k1_logo_cleaned' | 'k1_icon_cleaned') => {
    localStorage.removeItem(storageKey)
    localStorage.removeItem(cleanFlagKey)
    setter('')
    window.dispatchEvent(new Event('k1-branding'))
  }

  useEffect(() => {
    if (logoData && !localStorage.getItem('k1_logo_cleaned')) {
      applyAsset(logoData, 'k1_logo_dataurl', setLogoData, 'k1_logo_cleaned')
    }
    if (iconData && !localStorage.getItem('k1_icon_cleaned')) {
      applyAsset(iconData, 'k1_icon_dataurl', setIconData, 'k1_icon_cleaned')
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <div style={{ display: 'grid', gap: 16 }}>
      <h2 style={{ color: COLORS.text, fontSize: '1.2rem', fontWeight: 800, letterSpacing: '0.08em' }}>Settings</h2>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 12 }}>
        <div style={panelStyle}>
          <label style={labelStyle}>API Base</label>
          <input value={api} onChange={e=>setApi(e.target.value)} placeholder='http://localhost:8080' style={inputStyle}/>
          <label style={{ ...labelStyle, marginTop: 12 }}>Bearer Token</label>
          <input value={tok} onChange={e=>setTok(e.target.value)} placeholder='devtoken123' style={inputStyle}/>
          <button onClick={save} style={{
            marginTop: 12, padding: '8px 12px', borderRadius: 6,
            background: COLORS.secondary.main, color: COLORS.textInverse,
            border: `1px solid ${COLORS.border}`, fontWeight: 700, cursor: 'pointer',
          }}>
            Save
          </button>
          <p style={{ fontSize: '0.7rem', color: COLORS.textSecondary, marginTop: 8 }}>
            Token is used in Authorization header for protected endpoints.
          </p>
        </div>

        <div style={panelStyle}>
          <div style={{ color: COLORS.text, fontWeight: 800, marginBottom: 10 }}>Branding</div>
          <div style={{ display: 'grid', gap: 10 }}>
            <div>
              <label style={labelStyle}>Logo Image</label>
              <input
                type="file"
                accept="image/*"
                onChange={(e) => e.target.files?.[0] && handleAssetUpload(e.target.files[0], 'k1_logo_dataurl', setLogoData, 'k1_logo_cleaned')}
                style={{ color: COLORS.text, fontSize: '0.75rem' }}
              />
              {logoData && (
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 8 }}>
                  <img src={logoData} alt="Logo preview" style={{ width: 36, height: 36, objectFit: 'contain', border: `1px solid ${COLORS.border}`, borderRadius: 4 }} />
                  <button onClick={() => applyAsset(logoData, 'k1_logo_dataurl', setLogoData, 'k1_logo_cleaned')} style={{ background: 'transparent', border: `1px solid ${COLORS.border}`, color: COLORS.text, padding: '4px 8px', borderRadius: 4, cursor: 'pointer' }}>
                    Clean Background
                  </button>
                  <button onClick={() => clearAsset('k1_logo_dataurl', setLogoData, 'k1_logo_cleaned')} style={{ background: 'transparent', border: `1px solid ${COLORS.border}`, color: COLORS.text, padding: '4px 8px', borderRadius: 4, cursor: 'pointer' }}>
                    Remove
                  </button>
                </div>
              )}
            </div>
            <div>
              <label style={labelStyle}>Platform Icon (Favicon)</label>
              <input
                type="file"
                accept="image/*"
                onChange={(e) => e.target.files?.[0] && handleAssetUpload(e.target.files[0], 'k1_icon_dataurl', setIconData, 'k1_icon_cleaned')}
                style={{ color: COLORS.text, fontSize: '0.75rem' }}
              />
              {iconData && (
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 8 }}>
                  <img src={iconData} alt="Icon preview" style={{ width: 32, height: 32, objectFit: 'contain', border: `1px solid ${COLORS.border}`, borderRadius: 4 }} />
                  <button onClick={() => applyAsset(iconData, 'k1_icon_dataurl', setIconData, 'k1_icon_cleaned')} style={{ background: 'transparent', border: `1px solid ${COLORS.border}`, color: COLORS.text, padding: '4px 8px', borderRadius: 4, cursor: 'pointer' }}>
                    Clean Background
                  </button>
                  <button onClick={() => clearAsset('k1_icon_dataurl', setIconData, 'k1_icon_cleaned')} style={{ background: 'transparent', border: `1px solid ${COLORS.border}`, color: COLORS.text, padding: '4px 8px', borderRadius: 4, cursor: 'pointer' }}>
                    Remove
                  </button>
                </div>
              )}
            </div>
            {brandError && (
              <div style={{ color: COLORS.status.error, fontSize: '0.75rem' }}>{brandError}</div>
            )}
            <div style={{ fontSize: '0.7rem', color: COLORS.textSecondary }}>
              Images are stored locally in your browser and never uploaded unless you export them. Use this for safe, local branding.
            </div>
          </div>
        </div>
      </div>

      <div style={{ maxWidth: 720 }}>
        <KeyManagement />
      </div>

      <ProviderDiagnostics />
    </div>
  );
}


function ProviderDiagnostics(){
  const [cfg, setCfg] = React.useState<any>(null);
  const [err, setErr] = React.useState<string>('');
  React.useEffect(()=>{
    const tok = localStorage.getItem('k1_token') || localStorage.getItem('K1_DEV_TOKEN') || '';
    fetch('/state/config', { headers: { 'Authorization': tok? ('Bearer ' + tok): '' }})
      .then(r=>{ if(!r.ok) throw new Error(String(r.status)); return r.json(); })
      .then(setCfg)
      .catch(e=> setErr(String(e)));
  }, []);
  if(err) return <div className='text-amber-400 mt-3'>Diagnostics error: {err}</div>;
  if(!cfg) return <div className='opacity-70 mt-3'>Loading diagnostics…</div>;
  return (
    <div className='grid grid-cols-12 gap-3 mt-3'>
      <div className='col-span-6 p-3 bg-slate-950/60 rounded border border-slate-800'>
        <div className='font-semibold text-slate-300 mb-2'>Providers / Models</div>
        <div className='grid grid-cols-1 md:grid-cols-2 gap-2'>
          {Object.entries(cfg.providers.models).map(([k,v]: any)=> (
            <div key={k} className={`p-2 rounded border ${v.valid? 'border-emerald-500/40':'border-amber-500/40'} bg-black/30`}>
              <div className='flex justify-between'><span className='font-mono'>{k}</span><span className={`px-2 py-0.5 rounded text-xs ${v.valid? 'bg-emerald-600/40':'bg-amber-600/40'}`}>{v.valid? 'valid':'invalid'}</span></div>
              <div className='opacity-70 text-xs mt-1'>{v.name || 'unset'}</div>
            </div>
          ))}
        </div>
      </div>
      <div className='col-span-6 p-3 bg-slate-950/60 rounded border border-slate-800'>
        <div className='font-semibold text-slate-300 mb-2'>Vector Backend</div>
        <div>Backend: <span className='font-mono'>{cfg.vector.backend}</span></div>
        <div>Memory entries: <span className='font-mono'>{cfg.vector.mem_count}</span></div>
        <div className='mt-2 text-xs text-slate-400'>HiL Gate: <span className='font-mono'>{String(cfg.hil_gate_enforced)}</span>; Scope: <span className='font-mono'>{cfg.scope_policy}</span></div>
      </div>
    </div>
  );
}
