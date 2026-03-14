export function ValidationWarningsPanel({
  missingFields,
  warnings
}: {
  missingFields: string[];
  warnings: string[];
}) {
  return (
    <div className="space-y-2">
      {missingFields.length > 0 ? (
        <div className="rounded-md border border-danger/40 bg-danger/15 p-2 text-xs text-danger">
          <p className="font-semibold">Missing fields</p>
          <ul className="list-disc pl-5">
            {missingFields.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      ) : null}
      {warnings.length > 0 ? (
        <div className="rounded-md border border-review/40 bg-review/15 p-2 text-xs text-review">
          <p className="font-semibold">Warnings</p>
          <ul className="list-disc pl-5">
            {warnings.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}
