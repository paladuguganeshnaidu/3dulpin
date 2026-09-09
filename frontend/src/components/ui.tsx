import type { Property } from "../lib/types";

export function statusColor(status: string): string {
  const map: Record<string, string> = {
    approved: "bg-emerald-100 text-emerald-700 border-emerald-300",
    verified: "bg-emerald-100 text-emerald-700 border-emerald-300",
    submitted: "bg-sky-100 text-sky-700 border-sky-300",
    pending_verification: "bg-amber-100 text-amber-700 border-amber-300",
    draft: "bg-slate-100 text-slate-600 border-slate-300",
    rejected: "bg-rose-100 text-rose-700 border-rose-300",
  };
  return map[status] || "bg-slate-100 text-slate-600 border-slate-300";
}

export function sourceBadge(
  p: Pick<Property, "source_type" | "status" | "confidence" | "verified">
): { label: string; cls: string } {
  if (p.source_type === "synthetic_demo")
    return { label: "Synthetic Demo", cls: "bg-indigo-100 text-indigo-700 border-indigo-300" };
  if (p.source_type === "ai_derived")
    return { label: "AI-derived", cls: "bg-purple-100 text-purple-700 border-purple-300" };
  if (p.status === "pending_verification")
    return { label: "Pending", cls: "bg-amber-100 text-amber-700 border-amber-300" };
  if (p.status === "conflict" || p.source_type === "conflict")
    return { label: "Conflict", cls: "bg-rose-100 text-rose-700 border-rose-300" };
  if (p.verified) return { label: "Verified", cls: "bg-emerald-100 text-emerald-700 border-emerald-300" };
  return { label: "Pending", cls: "bg-amber-100 text-amber-700 border-amber-300" };
}

export function Badge({ children, cls }: { children: React.ReactNode; cls: string }) {
  return (
    <span className={`inline-block rounded border px-2 py-0.5 text-xs font-medium ${cls}`}>
      {children}
    </span>
  );
}

export function Field({ label, value }: { label: string; value?: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-4 border-b border-slate-100 py-1.5 text-sm">
      <span className="text-slate-500">{label}</span>
      <span className="text-right font-medium text-slate-800">{value ?? "—"}</span>
    </div>
  );
}

export function fmt(n: number | null | undefined, digits = 1): string {
  if (n === null || n === undefined || Number.isNaN(n)) return "—";
  return n.toLocaleString(undefined, { maximumFractionDigits: digits });
}
