import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, setToken } from "../api/client";

const DEMO_USERS = [
  { email: "reviewer@aicte.syn", role: "AICTE Reviewer" },
  { email: "supervisor@aicte.syn", role: "AICTE Supervisor" },
  { email: "auditor@aicte.syn", role: "Auditor" },
  { email: "admin@aicte.syn", role: "Admin" },
  { email: "operator1@syn.edu", role: "Operator (Inst 1)" },
];

export function Login() {
  const nav = useNavigate();
  const [email, setEmail] = useState("reviewer@aicte.syn");
  const [password, setPassword] = useState("demo1234");
  const [error, setError] = useState("");

  async function doLogin(em: string) {
    setError("");
    try {
      const res = await api.login(em, password);
      setToken(res.access_token);
      localStorage.setItem("apaar_role", res.role);
      nav("/linkage");
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="bg-amber-500 text-center text-xs font-semibold text-amber-950 py-1">
        SYNTHETIC DATA ONLY
      </div>
      <div className="mx-auto mt-16 max-w-md rounded-lg border bg-white p-8 shadow-sm">
        <h1 className="text-2xl font-bold">APAAR Sathi</h1>
        <p className="text-sm text-gray-500">verify without exposing</p>

        <div className="mt-6 space-y-3">
          <label className="block text-sm">
            Email
            <input
              className="mt-1 w-full rounded border px-3 py-2"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </label>
          <label className="block text-sm">
            Password
            <input
              type="password"
              className="mt-1 w-full rounded border px-3 py-2"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </label>
          {error && <p className="text-sm text-red-600">{error}</p>}
          <button
            className="w-full rounded bg-blue-600 py-2 text-white hover:bg-blue-700"
            onClick={() => doLogin(email)}
          >
            Sign in
          </button>
        </div>

        <div className="mt-6">
          <p className="mb-2 text-xs font-semibold text-gray-500">Demo quick-picks (password demo1234)</p>
          <div className="flex flex-wrap gap-2">
            {DEMO_USERS.map((u) => (
              <button
                key={u.email}
                className="rounded border px-2 py-1 text-xs hover:bg-gray-100"
                onClick={() => {
                  setEmail(u.email);
                  doLogin(u.email);
                }}
              >
                {u.role}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
