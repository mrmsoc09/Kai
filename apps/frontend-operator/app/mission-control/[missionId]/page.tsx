"use client";

import { useParams } from "next/navigation";

import { MissionControlWorkspace } from "@/components/missions/MissionControlWorkspace";

export default function MissionControlDetailPage() {
  const params = useParams<{ missionId: string }>();
  return <MissionControlWorkspace missionId={params.missionId} />;
}
