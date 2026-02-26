
import React, { useEffect, useState } from 'react'
import LogFilters from './LogFilters'
import TraceTable from './TraceTable'
import SummaryPanel from './SummaryPanel'
import EvidenceList from './EvidenceList'
import KnowledgeList from './KnowledgeList'
import { getLogIndex, getDecisionTrace, getSummary, getEvidenceLinks, getKnowledgeDelta, searchLogs } from '../../api/logs'
import type { DecisionTraceEntry, ReasoningSummary, EvidenceLink, KnowledgeDeltaEntry, LogCategory } from '../../api/types'

const DEMO_RUN = 'demo-run' // replace with selected run_id when wiring run selector

export default function LogsView(){
  const [runId] = useState<string>(DEMO_RUN)
  const [q, setQ] = useState('')
  const [category, setCategory] = useState<LogCategory|''>('')
  const [trace, setTrace] = useState<DecisionTraceEntry[]>([])
  const [summary, setSummary] = useState<ReasoningSummary|null>(null)
  const [ev, setEv] = useState<EvidenceLink[]>([])
  const [kd, setKd] = useState<KnowledgeDeltaEntry[]>([])

  useEffect(()=>{ (async()=>{
    try{
      await getLogIndex(runId) // ensures presence; ignore result for now
      const [t,s,e,k] = await Promise.all([
        getDecisionTrace(runId), getSummary(runId), getEvidenceLinks(runId), getKnowledgeDelta(runId)
      ])
      setTrace(t); setSummary(s); setEv(e); setKd(k)
    }catch{ setTrace([]); setSummary(null); setEv([]); setKd([]) }
  })() }, [runId])

  useEffect(()=>{ (async()=>{
    if(!q && !category){ return }
    try{ const res = await searchLogs(runId, q||undefined, category||undefined as any); setTrace(res) }catch{}
  })() }, [q, category, runId])

  return <div className='log-grid'>
    <div>
      <div className='log-panel'>
        <LogFilters q={q} onQ={setQ} category={category} onCategory={setCategory} />
        <TraceTable rows={trace} />
      </div>
      <div className='log-panel' style={{marginTop:12}}>
        <div className='widget-title' style={{marginBottom:8}}>Evidence Links</div>
        <EvidenceList rows={ev} />
      </div>
    </div>
    <div>
      <div className='widget-title' style={{marginBottom:8}}>Reasoning Summary</div>
      <SummaryPanel data={summary} />
      <div className='widget-title' style={{marginTop:12, marginBottom:8}}>Knowledge Delta</div>
      <KnowledgeList rows={kd} />
    </div>
  </div>
}
