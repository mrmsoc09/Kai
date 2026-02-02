
import React from 'react'
import Sidebar from './Sidebar'
import TopHUD from './TopHUD'
import ConsoleStrip from './ConsoleStrip'
import WizardPanel from './wizard/WizardPanel'
import { useWizard } from '../store/wizard'

export default function Layout({children}:{children: React.ReactNode}){
  const toggle = useWizard(s=> s.toggle)
  return <div className='app-shell'>
    <Sidebar />
    <TopHUD />
    <main className='content'>{children}</main>
    <button className='fab' onClick={toggle} title='Agent Zero Wizard'>✦</button>
    <WizardPanel />
    <ConsoleStrip />
  </div>
}
