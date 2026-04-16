"use client";

import { useParams } from "next/navigation";

import { MissionControlWorkspace } from "@/components/missions/MissionControlWorkspace";

export default function CampaignDetailPage() {
  const params = useParams<{ campaignId: string }>();
  return <MissionControlWorkspace missionId={params.campaignId} />;
}
