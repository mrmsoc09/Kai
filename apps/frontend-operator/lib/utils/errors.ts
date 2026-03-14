import { ApiError } from "@/lib/api/client";

export function getErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "Unknown error";
}

export function getErrorStatus(error: unknown): number | null {
  if (error instanceof ApiError) {
    return error.status;
  }
  return null;
}
