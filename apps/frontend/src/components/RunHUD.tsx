
import React from "react";
import StatusBadge from "../components/StatusBadge";

type Props = { run?: any };

export default function RunHUD({ run }: Props){
  if (!run) return (<div style={{padding:12}}>Run HUD</div>);
  const loops = run.loops || {};
  const decision = run.decision || {};
  const approval = run.approval || {};
  const ledger = run.ledger || {};
  const metrics = run.metrics || {};
  const box: React.CSSProperties = { border: "1px solid #e0e0e0", borderRadius: 8, padding: 12, display: "grid", gap: 8 };
  const row: React.CSSProperties = { display: "flex", alignItems: "center", justifyContent: "space-between" };
  const tag: React.CSSProperties = { background: "#f5f5f5", padding: "2px 6px", borderRadius: 4, marginLeft: 8 };
  return (
    <div style={box}>
      <div style={row}><strong>Loops</strong><div>
        <span style={tag}>GPEE: {loops.strategic?.step || "-"}</span>
        <span style={{...tag, marginLeft:8}}>OODA: {loops.tactical?.step || "-"}</span>
      </div></div>
      <div style={row}><strong>Decision</strong><div>
        <span style={tag}>Next: {decision.chosen?.name || "-"}</span>
        <span style={{...tag, marginLeft:8}}>Score: {decision.chosen?.score_total ?? "-"}</span>
      </div></div>
      <div style={row}><strong>Approval</strong><div>
        <span style={tag}>HiL Required: {String(approval.hil_required)}</span>
        <span style={{...tag, marginLeft:8}}>HiL Approved: {String(approval.hil_approved)}</span>
      </div></div>
      <div style={row}><strong>Ledger</strong><div>
        <span style={tag}>Assets: {ledger.assets?.length ?? 0}</span>
        <span style={{...tag, marginLeft:8}}>Hypotheses: {ledger.hypotheses?.length ?? 0}</span>
        <span style={{...tag, marginLeft:8}}>Evidence: {ledger.evidence?.length ?? 0}</span>
      </div></div>
      <div style={row}><strong>Metrics</strong><div>
        <span style={tag}>Chain cand.: {metrics.chain_candidate_count ?? 0}</span>
        <span style={{...tag, marginLeft:8}}>Evidence ratio: {metrics.evidence_completeness_ratio ?? 0}</span>
      </div></div>
    </div>
  );
}
