import React, { useEffect, useState } from 'react'

export default function GradientLogo(){
  const [logo, setLogo] = useState<string>(() => localStorage.getItem('k1_logo_dataurl') || '')

  useEffect(() => {
    const refresh = () => setLogo(localStorage.getItem('k1_logo_dataurl') || '')
    window.addEventListener('k1-branding', refresh)
    return () => window.removeEventListener('k1-branding', refresh)
  }, [])

  return (
    <div style={{display:'flex', alignItems:'center', gap:8}}>
      {logo ? (
        <img
          src={logo}
          alt="K1 Logo"
          style={{ width: 20, height: 20, objectFit: 'contain', borderRadius: 4, border: '1px solid #1E2A21' }}
        />
      ) : (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
          <defs>
            <linearGradient id="g" x1="0" y1="0" x2="24" y2="24" gradientUnits="userSpaceOnUse">
              <stop stopColor="#5A2E8A"/>
              <stop offset="0.5" stopColor="#D97706"/>
              <stop offset="1" stopColor="#355E3B"/>
            </linearGradient>
          </defs>
          <circle cx="12" cy="12" r="10" stroke="url(#g)" strokeWidth="2"/>
          <path d="M7 12h10M12 7v10" stroke="url(#g)" strokeWidth="2"/>
        </svg>
      )}
      <span className='brand'>K1 Command</span>
    </div>
  )
}
