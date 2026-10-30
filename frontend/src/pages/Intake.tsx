import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { PlaceholderTag, StatusBadge } from "../components/StatusBadge";
import { Table, Td } from "../components/Table";

export function Intake() {
  const { data, isLoading, error } = useQuery({ queryKey: ["intake"], queryFn: api.intake });
  if (isLoading) return <p>Evaluating intake…</p>;
  if (error) return <p className="text-red-600">{(error as Error).message}</p>;
  if (!data) return null;

  return (
    <div>
      <h2 className="mb-1 text-xl font-semibold">Intake Integrity Engine</h2>
      <p className="mb-4 text-sm text-gray-500">
        Each admission is counted against the approved intake effective on its admission date. A missing or
        outdated approval returns CANNOT_EVALUATE — never a flag.
      </p>

      <Table columns={["Institution", "Programme", "Year", "Numerator", "Limit", "Rule v", "Approval ref", "Result"]}>
        {data.results.map((r, i) => (
          <tr key={i}>
            <Td className="text-xs">{r.institution_name ?? r.institution}</Td>
            <Td>{r.program}</Td>
            <Td>
              {r.academic_year}
              <PlaceholderTag />
            </Td>
            <Td className="font-semibold">{r.numerator}</Td>
            <Td>{r.limit ?? "—"}</Td>
            <Td>{r.rule_version}</Td>
            <Td className="text-xs">{r.approval_reference || r.reason || "—"}</Td>
            <Td>
              <StatusBadge status={r.status} />
              {r.status === "OVER_LIMIT" && r.effective_limits_seen && r.effective_limits_seen.length > 1 && (
                <div className="mt-1 text-[10px] text-amber-700">
                  revised intake: earlier limit {r.limit} applied
                </div>
              )}
            </Td>
          </tr>
        ))}
      </Table>
    </div>
  );
}
