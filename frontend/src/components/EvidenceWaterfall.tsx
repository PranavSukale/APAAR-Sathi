import {
  Bar,
  BarChart,
  Cell,
  LabelList,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { PairEvidence } from "../api/client";
import { StatusBadge } from "./StatusBadge";

// "Why these two records match": per-field partial weights up/down, total, probability, band.
export function EvidenceWaterfall({ pair }: { pair: PairEvidence }) {
  const data = pair.evidence.map((e) => ({
    name: `${e.comparison} (${e.level})`,
    weight: e.weight,
  }));

  return (
    <div className="rounded border bg-white p-4">
      <div className="mb-3 flex items-center justify-between">
        <div>
          <div className="text-sm text-gray-500">Record pair (masked)</div>
          <div className="font-mono text-sm">
            {pair.masked_a} &nbsp;↔&nbsp; {pair.masked_b}
          </div>
        </div>
        <div className="text-right">
          <StatusBadge status={pair.band} label={`${pair.band} band`} />
          <div className="mt-1 text-sm">
            probability <span className="font-semibold">{(pair.probability * 100).toFixed(1)}%</span>
          </div>
          <div className="text-xs text-gray-500">total weight {pair.total_weight}</div>
        </div>
      </div>

      <ResponsiveContainer width="100%" height={240}>
        <BarChart data={data} layout="vertical" margin={{ left: 40, right: 40 }}>
          <XAxis type="number" />
          <YAxis type="category" dataKey="name" width={200} tick={{ fontSize: 11 }} />
          <Tooltip formatter={(v: number) => [`${v} bits`, "weight"]} />
          <ReferenceLine x={0} stroke="#666" />
          <Bar dataKey="weight">
            {data.map((d, i) => (
              <Cell key={i} fill={d.weight >= 0 ? "#2563eb" : "#dc2626"} />
            ))}
            <LabelList dataKey="weight" position="right" style={{ fontSize: 11 }} />
          </Bar>
        </BarChart>
      </ResponsiveContainer>

      <div className="mt-3 flex flex-wrap gap-4 text-xs text-gray-600">
        <span>
          <span className="inline-block h-2 w-3 bg-blue-600" /> pushes toward same person
        </span>
        <span>
          <span className="inline-block h-2 w-3 bg-red-600" /> pushes toward different people
        </span>
      </div>

      {(pair.baseline1_match !== undefined || pair.baseline2_match !== undefined) && (
        <div className="mt-3 rounded bg-gray-50 p-2 text-xs">
          <div className="font-semibold text-gray-600">Side-by-side with baselines</div>
          <div>exact-token baseline: {pair.baseline1_match ? "match" : "no match"}</div>
          <div>exact + fuzzy-name baseline: {pair.baseline2_match ? "match (would flag)" : "no match"}</div>
          {pair.baseline_false_positive && (
            <div className="mt-1 font-medium text-red-700">
              Naive baseline would FALSELY flag this common-name pair. Model keeps it Low.
            </div>
          )}
          {pair.exact_token_repeat && (
            <div className="mt-1 font-medium text-blue-700">
              Exact identifier repeat → always a rule exception for review.
            </div>
          )}
        </div>
      )}
    </div>
  );
}
