import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../api/client";
import { StatusBadge } from "../components/StatusBadge";

// Demo pairs are discovered from the linkage endpoint: a transfer pair and a concurrent pair.
export function Timeline() {
  const linkage = useQuery({ queryKey: ["linkage"], queryFn: api.linkagePairs });
  const [pair, setPair] = useState<{ a: string; b: string } | null>(null);

  // pick a pair: prefer a true-duplicate (shares token) which in the seed covers transfer/concurrent
  const candidates = linkage.data?.true_duplicates ?? [];
  const chosen = pair ?? (candidates[0] ? { a: candidates[0].record_a, b: candidates[0].record_b } : null);

  const tl = useQuery({
    queryKey: ["timeline", chosen?.a, chosen?.b],
    queryFn: () => api.timeline(chosen!.a, chosen!.b),
    enabled: !!chosen,
  });

  if (linkage.isLoading) return <p>Loading…</p>;

  return (
    <div>
      <h2 className="mb-1 text-xl font-semibold">Enrolment Timeline Integrity</h2>
      <p className="mb-4 text-sm text-gray-500">
        Episodes drawn as date bars. A recorded transfer is cleared; an unexplained overlap is flagged for review.
      </p>

      <div className="mb-4 flex flex-wrap gap-2">
        {candidates.slice(0, 6).map((c) => (
          <button
            key={c.record_a + c.record_b}
            className="rounded border px-2 py-1 text-xs hover:bg-gray-100"
            onClick={() => setPair({ a: c.record_a, b: c.record_b })}
          >
            {c.masked_a} ↔ {c.masked_b}
          </button>
        ))}
      </div>

      {tl.data && <TimelineBars data={tl.data} />}
    </div>
  );
}

function TimelineBars({ data }: { data: Awaited<ReturnType<typeof api.timeline>> }) {
  const bars = data.bars;
  if (bars.length === 0) return <p className="text-sm text-gray-500">No episodes for this pair.</p>;

  const dates = bars.flatMap((b) => [new Date(b.start), b.end ? new Date(b.end) : new Date()]);
  const min = Math.min(...dates.map((d) => d.getTime()));
  const max = Math.max(...dates.map((d) => d.getTime()));
  const span = max - min || 1;
  const pct = (t: number) => ((t - min) / span) * 100;

  return (
    <div className="rounded border bg-white p-4">
      <div className="space-y-4">
        {bars.map((b) => {
          const start = new Date(b.start).getTime();
          const end = b.end ? new Date(b.end).getTime() : max;
          return (
            <div key={b.episode_id}>
              <div className="mb-1 flex justify-between text-xs text-gray-500">
                <span>Institution …{b.institution} {b.transfer_from && `(transfer from …${b.transfer_from})`}</span>
                <span>
                  {b.start} → {b.end ?? "ongoing"} · {b.status}
                </span>
              </div>
              <div className="relative h-6 rounded bg-gray-100">
                <div
                  className="absolute h-6 rounded bg-blue-500"
                  style={{ left: `${pct(start)}%`, width: `${Math.max(pct(end) - pct(start), 2)}%` }}
                />
              </div>
            </div>
          );
        })}
      </div>

      <div className="mt-4 space-y-2">
        {data.findings.map((f, i) => (
          <div key={i} className="flex items-start gap-2 text-sm">
            <StatusBadge
              status={f.rule_code === "TL-OVERLAP" ? "OVER_LIMIT" : f.rule_code === "TL-TRANSFER-OK" ? "WITHIN_LIMIT" : "CANNOT_EVALUATE"}
              label={f.rule_code}
            />
            <span className="text-xs text-gray-600">{JSON.stringify(f.evidence)}</span>
          </div>
        ))}
        {data.findings.length === 0 && <p className="text-sm text-gray-500">No timeline findings.</p>}
      </div>
    </div>
  );
}
