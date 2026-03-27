import { Suspense, lazy } from "react";
import { Routes, Route } from "react-router-dom";
import Landing from "@/pages/Landing";
import { RequireAuth } from "@/components/RequireAuth";
import NotFound from "@/pages/NotFound";

const Dashboard = lazy(() => import("@/pages/Dashboard"));
const PortfolioView = lazy(() =>
  import("@/pages/PortfolioView").then((module) => ({ default: module.PortfolioView })),
);
const ControlPanel = lazy(() => import("@/pages/ControlPanel"));

function RouteFallback() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-black text-sm text-zinc-400">
      Loading page...
    </div>
  );
}

export default function App() {
  return (
    <Suspense fallback={<RouteFallback />}>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route
          path="/dashboard"
          element={
            <RequireAuth>
              <Dashboard />
            </RequireAuth>
          }
        />
        <Route
          path="/dashboard/:id"
          element={
            <RequireAuth>
              <PortfolioView />
            </RequireAuth>
          }
        />
        <Route
          path="/control-panel"
          element={
            <RequireAuth allowedRoles={["manager", "admin"]}>
              <ControlPanel />
            </RequireAuth>
          }
        />
        <Route path="*" element={<NotFound />} />
      </Routes>
    </Suspense>
  );
}
