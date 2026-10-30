import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api, PairEvidence } from "../api/client";
import { EvidenceWaterfall } from "../components/EvidenceWaterfall";
import { StatusBadge } from "../components/StatusBadge";
import { Table, Td } from "../components/Table";

export function Linkage() {
  const { data, isLoading, error } = useQuery({ queryKey: ["linkage"], queryFn: api.linkagePairs });
  const [selected, setSelected] = useState<PairEvidence | null>(null);

  if (isLoading) return <p>Loading candidate pairs…</p>;
  if (error) return <p className="text-red-600">{(error as Error).message}</p>;
  if (!data) return null;

  const current = selected ?? data.true_duplicates[0] ?? data.pairs[0];

  function PairRows({ list, title }: { list: PairEvidence[]; title: string }) {
    return (
      <div className="mb-4">
        <h3 className="mb-1 text-sm font-semibold text-gray-600">{title}</h3>
        <Table columns={["Records (masked)", "Band", "Prob", "Baseline2", ""]}>
          {list.slice(0, 6).map((p) => (
            <tr key={p.record_a + p.record_b} className="hover:bg-blue-50">
              <Td className="font-mono text-xs">
                {p.masked_a} ↔ {p.masked_b}
              </Td>
              <Td>
                <StatusBadge status={p.band} />
              </Td>
              <Td>{(p.probability * 100).toFixed(0)}%</Td>
              <Td className="text-xs">{p.baseline2_match ? "would flag" : "—"}</Td>
              <Td>
                <button className="rounded border px-2 py-0.5 text-xs hover:bg-white" onClick={() => setSelected(p)}>
                  View evidence
                </button>
              </Td>
            </tr>
          ))}
        </Table>
      </div>
    );
  }

  return (
    <div>
      <h2 className="mb-1 text-xl font-semibold">Explainable Identity Linkage</h2>
      <p className="mb-4 text-sm text-gray-500">
        {data.candidate_count.toLocaleString()} candidate pairs from keyed blocking. Every candidate carries a
        full per-field evidence breakdown. No records are ever merged automatically.
      </p>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <div>
          <PairRows list={data.true_duplicates} title="True duplicates (model + rule agree)" />
          <PairRows
            list={data.baseline_false_positives}
            title="Common-name trap: naive baseline false-flags, model correct"
          />
        </div>
        <div>{current && <EvidenceWaterfall pair={current} />}</div>
      </div>
    </div>
  );
}
