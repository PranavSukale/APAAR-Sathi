// Status is never colour-only: each badge pairs an icon/symbol with a text label.
const STYLES: Record<string, { cls: string; icon: string }> = {
  High: { cls: "bg-red-100 text-red-800 border-red-300", icon: "●" },
  Medium: { cls: "bg-amber-100 text-amber-800 border-amber-300", icon: "◐" },
  Low: { cls: "bg-gray-100 text-gray-700 border-gray-300", icon: "○" },
  OVER_LIMIT: { cls: "bg-red-100 text-red-800 border-red-300", icon: "▲" },
  WITHIN_LIMIT: { cls: "bg-green-100 text-green-800 border-green-300", icon: "✓" },
  CANNOT_EVALUATE: { cls: "bg-slate-100 text-slate-700 border-slate-300", icon: "—" },
  PASS: { cls: "bg-green-100 text-green-800 border-green-300", icon: "✓" },
  FAIL: { cls: "bg-red-100 text-red-800 border-red-300", icon: "✕" },
  FORMAT_VALID: { cls: "bg-blue-100 text-blue-800 border-blue-300", icon: "ℹ" },
  MOCK: { cls: "bg-purple-100 text-purple-800 border-purple-300", icon: "⚙" },
};

export function StatusBadge({ status, label }: { status: string; label?: string }) {
  const s = STYLES[status] || { cls: "bg-gray-100 text-gray-700 border-gray-300", icon: "•" };
  return (
    <span
      className={`inline-flex items-center gap-1 rounded border px-2 py-0.5 text-xs font-medium ${s.cls}`}
      role="status"
    >
      <span aria-hidden>{s.icon}</span>
      {label ?? status}
    </span>
  );
}

export function PlaceholderTag() {
  return (
    <span className="ml-2 inline-flex items-center rounded border border-dashed border-amber-400 bg-amber-50 px-1.5 py-0.5 text-[10px] font-medium text-amber-700">
      placeholder, pending validation
    </span>
  );
}
