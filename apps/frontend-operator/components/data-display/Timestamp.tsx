import { formatTimestamp } from "@/lib/utils/formatting";

export function Timestamp({ value }: { value: string | null | undefined }) {
  return <span>{formatTimestamp(value)}</span>;
}
