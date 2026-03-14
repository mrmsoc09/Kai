import { FormEvent } from "react";

import { isUuid } from "@/lib/utils";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

export function ProgramUuidFilterCard({
  inputValue,
  onInputChange,
  onApply,
  onClear,
  title = "Program Filter",
  applyLabel = "Apply Program Filter",
  activeProgramId
}: {
  inputValue: string;
  onInputChange: (value: string) => void;
  onApply: (programId: string | undefined) => void;
  onClear?: () => void;
  title?: string;
  applyLabel?: string;
  activeProgramId?: string;
}) {
  const trimmed = inputValue.trim();
  const invalid = trimmed.length > 0 && !isUuid(trimmed);

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (trimmed.length === 0) {
      onApply(undefined);
      return;
    }
    if (invalid) {
      return;
    }
    onApply(trimmed);
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <form className="grid gap-2 md:grid-cols-[1fr_auto_auto]" onSubmit={handleSubmit}>
          <Input
            value={inputValue}
            onChange={(event) => onInputChange(event.target.value)}
            placeholder="program UUID (optional)"
            aria-invalid={invalid}
          />
          <Button type="submit" variant="secondary" disabled={invalid}>
            {applyLabel}
          </Button>
          <Button
            type="button"
            variant="outline"
            onClick={() => {
              onInputChange("");
              onApply(undefined);
              onClear?.();
            }}
          >
            Clear
          </Button>
        </form>
        {invalid ? <p className="text-xs text-danger">Program filter must be a valid UUID.</p> : null}
        {activeProgramId ? (
          <p className="font-mono text-xs text-muted">active filter: {activeProgramId}</p>
        ) : (
          <p className="text-xs text-muted">active filter: all programs</p>
        )}
      </CardContent>
    </Card>
  );
}
