import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

export function ProgramFilterCard({
  value,
  onChange,
  title = "Program Filter",
  placeholder = "program UUID (optional)"
}: {
  value: string;
  onChange: (value: string) => void;
  title?: string;
  placeholder?: string;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <Input value={value} onChange={(event) => onChange(event.target.value)} placeholder={placeholder} />
      </CardContent>
    </Card>
  );
}
