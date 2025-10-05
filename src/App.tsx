import { Routes, Route, Navigate } from "react-router-dom";
import Landing from "@/pages/Landing";
import Dashboard from "@/pages/Dashboard";
import { PortfolioView } from "@/pages/PortfolioView";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/dashboard" element={<Dashboard />} />
      <Route path="/dashboard/:id" element={<PortfolioView />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
