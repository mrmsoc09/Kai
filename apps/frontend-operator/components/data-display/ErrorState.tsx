import { ApiError } from "@/lib/api/client";
import { getErrorMessage, getErrorStatus } from "@/lib/utils/errors";

export function ErrorState({
  error,
  title = "Request failed"
}: {
  error: unknown;
  title?: string;
}) {
  const message = getErrorMessage(error);
  const status = getErrorStatus(error);
  const detail = error instanceof ApiError ? error.payload.detail : null;
  return (
    <div className="rounded-md border border-danger/40 bg-danger/15 p-3 text-sm text-danger">
      <p className="font-semibold">{title}</p>
      <p>{message}</p>
      {status ? <p className="mt-1 text-xs">HTTP {status}</p> : null}
      {typeof detail === "string" && detail !== message ? <p className="mt-1 text-xs">{detail}</p> : null}
    </div>
  );
}
