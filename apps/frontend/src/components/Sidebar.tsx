
import React from 'react'
import { NavLink } from 'react-router-dom'

const links = [
  {to:'/docs', label:'Docs'},
  {to:'/wizard', label:'Wizard'},
  {to:'/dashboard', label:'Dashboard'},
  {to:'/operations', label:'Operations'},
  {to:'/operations/approvals', label:'HiL Approvals'},
  {to:'/arsenal', label:'Arsenal'},
  {to:'/intelligence', label:'Intelligence'},
  {to:'/mcp-registry', label:'MCP Registry'},
  {to:'/persona-market', label:'Persona Market'},
  {to:'/logs', label:'Logs'},
  {to:'/settings', label:'Settings'},
]

export default function Sidebar(){
  return <aside className='sidebar'>
    <div className='title'>K1</div>
    <div className='section'>Navigation</div>
    <div className='nav'>
      {links.map(l=> <NavLink key={l.to} to={l.to} className={({isActive})=> isActive? 'active':'' }>{l.label}</NavLink>)}
    </div>
  </aside>
}
