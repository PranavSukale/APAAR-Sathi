import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { api } from "../api/client";
import { StatusBadge } from "../components/StatusBadge";
import { Table, Td } from "../components/Table";

const PURPOSES = [
  "DUPLICATE_CONFIRMATION",
  "CONCURRENT_ENROLMENT_REVIEW",
  "INTAKE_VERIFICATION",
  "EXTERNAL_VERIFICATION_PREP",
];

export function Reveal() {
  const role = localStorage.getItem("apaar_role") || "";
  const linkage = useQuery({ queryKey: ["linkage"], queryFn: api.linkagePairs });
  const reveals = useQuery({ queryKey: ["reveals"], queryFn: api.reveals });
  const [purpose, setPurpose] = useState(PURPOSES[0]);
  const [detail, setDetail] = useState("sample review");
  const [msg, setMsg] = useState("");
  const [revealed, setRevealed] = useState<{ name: string; apaar: string; expires_at: string } | null>(null);
  const [countdown, setCountdown] = useState<number | null>(null);

  const sampleRecord = linkage.data?.pairs[0]?.record_a;

  useEffect(() => {
    if (countdown === null) return;
    if (countdown <= 0) return;
    const t = setTimeout(() => setCountdown((c) => (c ?? 0) - 1), 1000);
    return () => clearTimeout(t);
  }, [countdown]);

  async function requestReveal() {
    if (!sampleRecord) return;
    setMsg("");
    try {
      const rr = await api.createReveal(sampleRecord, purpose, detail);
      setMsg(`Reveal requested (${rr.id.slice(0, 8)}). A supervisor must approve.`);
      reveals.refetch();
    } catch (e) {
      setMsg((e as Error).message);
    }
  }

  async function approve(id: string) {
    try {
      await api.approveReveal(id);
      setMsg("Approved. Single-use, expires shortly.");
      reveals.refetch();
    } catch (e) {
      setMsg((e as Error).message);
    }
  }

  async function consume(id: string) {
    try {
      const out = await api.consumeReveal(id);
      setRevealed(out);
      const secs = Math.max(0, Math.floor((new Date(out.expires_at).getTime() - Date.now()) / 1000));
      setCountdown(secs);
      reveals.refetch();
    } catch (e) {
      setMsg((e as Error).message);
    }
  }

  return (
    <div>
      <h2 className="mb-1 text-xl font-semibold">Controlled Reveal</h2>
      <p className="mb-4 text-sm text-gray-500">
        Purpose-bound, dual-approved, single-use and expiring. Self-approval is rejected. Every step is audited.
      </p>

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="rounded border bg-white p-4">
          <h3 className="mb-2 text-sm font-semibold">Request a reveal</h3>
          <label className="block text-sm">
            Purpose
            <select className="mt-1 w-full rounded border px-2 py-1" value={purpose} onChange={(e) => setPurpose(e.target.value)}>
              {PURPOSES.map((p) => (
                <option key={p}>{p}</option>
              ))}
            </select>
          </label>
          <label className="mt-2 block text-sm">
            Detail
            <input className="mt-1 w-full rounded border px-2 py-1" value={detail} onChange={(e) => setDetail(e.target.value)} />
          </label>
          <button
            className="mt-3 rounded bg-blue-600 px-3 py-1.5 text-sm text-white hover:bg-blue-700 disabled:opacity-50"
            onClick={requestReveal}
            disabled={role !== "AICTE_REVIEWER" && role !== "AICTE_SUPERVISOR"}
          >
            Request reveal
          </button>
          {msg && <p className="mt-2 text-xs text-gray-600">{msg}</p>}

          {revealed && (
            <div className="mt-4 rounded border-2 border-dashed border-purple-400 bg-purple-50 p-3">
              <div className="text-xs font-semibold text-purple-700">One-time reveal</div>
              <div className="font-mono text-sm">name: {revealed.name}</div>
              <div className="font-mono text-sm">apaar: {revealed.apaar}</div>
              <div className="mt-1 text-xs text-purple-700">
                expires in {countdown}s · single-use (already consumed)
              </div>
            </div>
          )}
        </div>

        <div>
          <h3 className="mb-2 text-sm font-semibold">Approval queue</h3>
          <Table columns={["Purpose", "Status", "Expires", ""]}>
            {(reveals.data ?? []).map((r) => (
              <tr key={r.id}>
                <Td className="text-xs">{r.purpose}</Td>
                <Td>
                  <StatusBadge
                    status={r.status === "CONSUMED" ? "PASS" : r.status === "APPROVED" ? "FORMAT_VALID" : "CANNOT_EVALUATE"}
                    label={r.status}
                  />
                </Td>
                <Td className="text-xs">{r.expires_at ? new Date(r.expires_at).toLocaleTimeString() : "—"}</Td>
                <Td>
                  {r.status === "REQUESTED" && role === "AICTE_SUPERVISOR" && (
                    <button className="rounded border px-2 py-0.5 text-xs" onClick={() => approve(r.id)}>
                      Approve
                    </button>
                  )}
                  {r.status === "APPROVED" && (
                    <button className="rounded border px-2 py-0.5 text-xs" onClick={() => consume(r.id)}>
                      Reveal once
                    </button>
                  )}
                </Td>
              </tr>
            ))}
          </Table>
          <p className="mt-2 text-xs text-gray-500">
            Approve as the Supervisor demo user, then reveal once. A second reveal is blocked.
          </p>
        </div>
      </div>
    </div>
  );
}
