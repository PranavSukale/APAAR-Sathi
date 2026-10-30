import { NavLink, useNavigate } from "react-router-dom";
import { ReactNode } from "react";
import { setToken } from "../api/client";

const NAV = [
  { to: "/linkage", label: "Identity Linkage" },
  { to: "/timeline", label: "Enrolment Timeline" },
  { to: "/intake", label: "Intake Integrity" },
  { to: "/reveal", label: "Controlled Reveal" },
  { to: "/proof", label: "Privacy & Integrity" },
];

export function Layout({ children }: { children: ReactNode }) {
  const nav = useNavigate();
  const role = localStorage.getItem("apaar_role") || "";
  return (
    <div className="min-h-screen bg-gray-50 text-gray-800">
      <div className="bg-amber-500 text-center text-xs font-semibold text-amber-950 py-1">
        SYNTHETIC DATA ONLY · no Aadhaar/UIDAI · no live APAAR/DigiLocker · flags are review signals, never proof
      </div>
      <header className="flex items-center justify-between border-b bg-white px-4 py-3">
        <div className="flex items-center gap-3">
          <span className="text-lg font-bold">APAAR Sathi</span>
          <span className="text-xs text-gray-500">verify without exposing</span>
        </div>
        <div className="flex items-center gap-3 text-sm">
          <span className="rounded bg-gray-100 px-2 py-0.5 text-xs">{role}</span>
          <button
            className="rounded border px-2 py-1 text-xs hover:bg-gray-100"
            onClick={() => {
              setToken(null);
              localStorage.removeItem("apaar_role");
              nav("/login");
            }}
          >
            Sign out
          </button>
        </div>
      </header>
      <div className="flex">
        <nav className="w-52 shrink-0 border-r bg-white p-2">
          {NAV.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              className={({ isActive }) =>
                `block rounded px-3 py-2 text-sm ${
                  isActive ? "bg-blue-600 text-white" : "hover:bg-gray-100"
                }`
              }
            >
              {n.label}
            </NavLink>
          ))}
        </nav>
        <main className="flex-1 p-6">{children}</main>
      </div>
    </div>
  );
}
