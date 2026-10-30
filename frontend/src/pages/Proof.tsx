import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api, AuditResult, PrivacyProof } from "../api/client";
import { StatusBadge } from "../components/StatusBadge";
import { Table, Td } from "../components/Table";

export function Proof() {
  const [proof, setProof] = useState<PrivacyProof | null>(null);
  const [audit, setAudit] = useState<AuditResult | null>(null);
  const bench = useQuery({ queryKey: ["benchmark"], queryFn: api.benchmark });

  return (
    <div>
      <h2 className="mb-1 text-xl font-semibold">Privacy &amp; Integrity — Proof</h2>
      <p className="mb-4 text-sm text-gray-500">
        Measurable privacy: no raw identifiers at rest, a tamper-evident audit chain, and a benchmark against the
        naive baseline.
      </p>

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="rounded border bg-white p-4">
          <h3 className="mb-2 text-sm font-semibold">Privacy scan</h3>
          <button
            className="rounded bg-blue-600 px-3 py-1.5 text-sm text-white hover:bg-blue-700"
            onClick={async () => setProof(await api.privacyProof())}
          >
            Run privacy scan
          </button>
          {proof && (
            <div className="mt-3">
              <StatusBadge status={proof.passed ? "PASS" : "FAIL"} label={proof.passed ? "No canary leaks" : "Leak found"} />
              <div className="mt-2 space-y-1 text-xs">
                {proof.checks.map((c) => (
                  <div key={c.target} className="flex justify-between">
                    <span>{c.target}</span>
                    <span>
                      {c.pass ? "clean" : `hits: ${c.hits.join(", ")}`}
                      {c.rows_scanned != null && ` (${c.rows_scanned} rows)`}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        <div className="rounded border bg-white p-4">
          <h3 className="mb-2 text-sm font-semibold">Audit chain</h3>
          <button
            className="rounded bg-blue-600 px-3 py-1.5 text-sm text-white hover:bg-blue-700"
            onClick={async () => setAudit(await api.auditVerify())}
          >
            Verify audit chain
          </button>
          {audit && (
            <div className="mt-3">
              <StatusBadge status={audit.valid ? "PASS" : "FAIL"} label={audit.valid ? "Chain intact" : "Tamper detected"} />
              {audit.valid ? (
                <p className="mt-2 text-xs text-gray-600">{audit.events} events verified from genesis.</p>
              ) : (
                <p className="mt-2 text-xs text-red-700">
                  First mismatch at seq {audit.first_mismatch_seq}. Expected {audit.expected_hash?.slice(0, 12)}…,
                  stored {audit.stored_hash?.slice(0, 12)}…
                </p>
              )}
            </div>
          )}
        </div>
      </div>

      <div className="mt-6 rounded border bg-white p-4">
        <h3 className="mb-2 text-sm font-semibold">Linkage benchmark — model vs naive baseline (SYNTHETIC)</h3>
        {bench.isLoading && <p className="text-sm">Loading benchmark…</p>}
        {bench.data && !("error" in bench.data) && (
          <>
            <p className="mb-2 text-xs text-gray-500">
              n = {bench.data.n_records.toLocaleString()} records · {bench.data.candidate_pairs.toLocaleString()} candidate pairs
            </p>
            <Table columns={["Mode", "Precision", "Recall", "F1", "False-positive rate"]}>
              {Object.entries(bench.data.modes).map(([name, m]) => (
                <tr key={name} className={name.includes("high_band") ? "bg-blue-50 font-medium" : ""}>
                  <Td>{name}</Td>
                  <Td>{m.precision}</Td>
                  <Td>{m.recall}</Td>
                  <Td>{m.f1}</Td>
                  <Td>{m.false_positive_rate}</Td>
                </tr>
              ))}
            </Table>
            <div className="mt-4">
              <h4 className="mb-1 text-xs font-semibold text-gray-600">Model PR curve</h4>
              <ResponsiveContainer width="100%" height={220}>
                <LineChart data={bench.data.pr_curve_model}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="recall" name="recall" type="number" domain={[0, 1]} tick={{ fontSize: 11 }} label={{ value: "recall", position: "insideBottom", offset: -2, fontSize: 11 }} />
                  <YAxis dataKey="precision" name="precision" type="number" domain={[0, 1]} tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Line type="monotone" dataKey="precision" stroke="#2563eb" dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
