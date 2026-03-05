
import React from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import { useStore } from '../store/system'
import { authLogout } from '../lib/api'

const links = [
  {to:'/dashboard', label:'Dashboard'},
  {to:'/opportunities', label:'Opportunities'},
  {to:'/workflows', label:'Active Hunts'},
  {to:'/findings', label:'Findings'},
  {to:'/operations', label:'Operations'},
  {to:'/operations/approvals', label:'HiL Approvals'},
  {to:'/scopes', label:'Scopes'},
  {to:'/arsenal', label:'Arsenal'},
  {to:'/intelligence', label:'Intelligence'},
  {to:'/programs', label:'BBP Archive'},
  {to:'/mcp-registry', label:'MCP Registry'},
  {to:'/persona-market', label:'Persona Market'},
  {to:'/logs', label:'Logs'},
  {to:'/settings', label:'Settings'},
  {to:'/docs', label:'Docs'},
  {to:'/wizard', label:'Wizard'},
]

export default function Sidebar(){
  const logout = useStore((s) => s.logout)
  const user = useStore((s) => s.auth.user)
  const navigate = useNavigate()

  const handleLogout = async () => {
    try { await authLogout() } catch (_) { /* ignore */ }
    logout()
    navigate('/login', { replace: true })
  }

  return <aside className='sidebar'>
    <div className='title'>K1</div>
    {user && <div style={{ fontSize: '0.65rem', color: '#4a5568', padding: '0 12px', marginBottom: 8, letterSpacing: '0.05em' }}>
      {user.id} · {user.roles[0] ?? 'user'}
    </div>}
    <div className='section'>Navigation</div>
    <div className='nav'>
      {links.map(l=> <NavLink key={l.to} to={l.to} className={({isActive})=> isActive? 'active':'' }>{l.label}</NavLink>)}
    </div>
    <button
      onClick={handleLogout}
      style={{
        margin: '12px 10px 0',
        padding: '6px 10px',
        background: 'transparent',
        border: '1px solid #1e2330',
        borderRadius: 4,
        color: '#4a5568',
        fontFamily: 'inherit',
        fontSize: '0.75rem',
        cursor: 'pointer',
        letterSpacing: '0.08em',
        width: 'calc(100% - 20px)',
      }}
    >
      SIGN OUT
    </button>
  </aside>
}
