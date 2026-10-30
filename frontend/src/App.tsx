import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Navigate, Route, BrowserRouter as Router, Routes } from "react-router-dom";
import { getToken } from "./api/client";
import { Layout } from "./components/Layout";
import { Intake } from "./pages/Intake";
import { Linkage } from "./pages/Linkage";
import { Login } from "./pages/Login";
import { Proof } from "./pages/Proof";
import { Reveal } from "./pages/Reveal";
import { Timeline } from "./pages/Timeline";

const qc = new QueryClient({ defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false } } });

function Protected({ children }: { children: JSX.Element }) {
  return getToken() ? <Layout>{children}</Layout> : <Navigate to="/login" replace />;
}

export default function App() {
  return (
    <QueryClientProvider client={qc}>
      <Router>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/linkage" element={<Protected><Linkage /></Protected>} />
          <Route path="/timeline" element={<Protected><Timeline /></Protected>} />
          <Route path="/intake" element={<Protected><Intake /></Protected>} />
          <Route path="/reveal" element={<Protected><Reveal /></Protected>} />
          <Route path="/proof" element={<Protected><Proof /></Protected>} />
          <Route path="*" element={<Navigate to="/linkage" replace />} />
        </Routes>
      </Router>
    </QueryClientProvider>
  );
}
