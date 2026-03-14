import type { FindingReviewActionRequest } from "@/lib/types";

import { ReviewActionForm } from "@/components/forms/ReviewActionForm";

export function FindingReviewPanel({
  loading = false,
  onSubmit
}: {
  loading?: boolean;
  onSubmit: (body: FindingReviewActionRequest) => void;
}) {
  return <ReviewActionForm loading={loading} onSubmit={onSubmit} />;
}
