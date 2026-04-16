import { Alert } from "@/components/ui/alert";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export function IntentionDisplayCard({
  intention,
  justification,
  expectedImpact,
  safetyConstraints
}: {
  intention: string;
  justification?: string;
  expectedImpact?: string;
  safetyConstraints?: string;
}) {
  const hasIntention = intention.trim().length > 0;
  return (
    <Card className={hasIntention ? "" : "border-danger/60"}>
      <CardHeader className="pb-2">
        <CardTitle>Intention</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2 text-sm">
        {hasIntention ? (
          <p className="text-foreground">{intention}</p>
        ) : (
          <Alert className="border-danger/50 bg-danger/10 text-danger">
            This approval request is missing explicit intention metadata and should not be approved without clarification.
          </Alert>
        )}
        {justification ? <p className="text-muted">Justification: {justification}</p> : null}
        {expectedImpact ? <p className="text-muted">Expected impact: {expectedImpact}</p> : null}
        {safetyConstraints ? <p className="text-muted">Safety constraints: {safetyConstraints}</p> : null}
      </CardContent>
    </Card>
  );
}
