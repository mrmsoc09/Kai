import React from 'react';
import WizardChat from '../components/WizardChat';

export default function Wizard(){
  return (
    <div className='h-full relative'>
      <div className='absolute inset-0 pointer-events-none laser-overlay' />
      <div className='h-full grid grid-cols-12 gap-4'>
        <div className='col-span-8'>
          <h2 className='text-xl mb-2 font-semibold text-cyan-300'>Agent Zero Wizard</h2>
          <WizardChat />
        </div>
        <div className='col-span-4 space-y-3'>
          <section className='p-3 bg-slate-950/60 rounded border border-slate-800'>
            <h3 className='text-sm uppercase tracking-wider text-slate-400'>Quick Actions</h3>
            <ul className='mt-2 space-y-1 text-slate-200'>
              <li>• Start Recon Plan (HiL)</li>
              <li>• Stage Evidence Package</li>
              <li>• Submit to TheHive Draft</li>
            </ul>
          </section>
          <section className='p-3 bg-slate-950/60 rounded border border-slate-800'>
            <h3 className='text-sm uppercase tracking-wider text-slate-400'>Governance</h3>
            <p className='text-slate-300 text-sm'>All outbound comms route via Agent Zero (HiL enforced). No auto-submits.</p>
          </section>
        </div>
      </div>
    </div>
  )
}
