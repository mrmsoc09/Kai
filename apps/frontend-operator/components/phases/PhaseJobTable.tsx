import type { CampaignStatusResponse } from "@/lib/types";

import { DataTable } from "@/components/data-display/DataTable";
import { PhaseStatusBadge } from "@/components/status/PhaseStatusBadge";
import { Td, Th } from "@/components/ui/table";

export function PhaseJobTable({ jobs }: { jobs: CampaignStatusResponse["phase_jobs"] }) {
  return (
    <DataTable>
      <thead>
        <tr>
          <Th>Phase</Th>
          <Th>Order</Th>
          <Th>Status</Th>
          <Th>Depends On</Th>
          <Th>Approval Required</Th>
          <Th>Worker Task</Th>
        </tr>
      </thead>
      <tbody>
        {jobs.map((job) => (
          <tr key={job.id}>
            <Td>{job.phase_name}</Td>
            <Td>{job.phase_order}</Td>
            <Td>
              <PhaseStatusBadge status={job.status} />
            </Td>
            <Td className="font-mono text-xs">{job.depends_on_job_id ?? "-"}</Td>
            <Td>{job.approval_required ? "yes" : "no"}</Td>
            <Td className="font-mono text-xs">{job.worker_task_id ?? "-"}</Td>
          </tr>
        ))}
      </tbody>
    </DataTable>
  );
}
