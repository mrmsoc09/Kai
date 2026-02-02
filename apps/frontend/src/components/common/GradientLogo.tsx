import React from 'react'
export default function GradientLogo(){
  return <div style={{display:'flex', alignItems:'center', gap:8}}>
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
      <defs>
        <linearGradient id="g" x1="0" y1="0" x2="24" y2="24" gradientUnits="userSpaceOnUse">
          <stop stopColor="#7a2a7a"/>
          <stop offset="0.5" stopColor="#2a5a7a"/>
          <stop offset="1" stopColor="#2d5a3f"/>
        </linearGradient>
      </defs>
      <circle cx="12" cy="12" r="10" stroke="url(#g)" strokeWidth="2"/>
      <path d="M7 12h10M12 7v10" stroke="url(#g)" strokeWidth="2"/>
    </svg>
    <span className='brand'>K1 Command</span>
  </div>
}
