// components/RequireAuth.tsx
import React, { useEffect, useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { authMe, clearAccessToken, getAccessToken } from "@/Api";

export function RequireAuth({ children }: { children: JSX.Element }) {
  const nav = useNavigate();
  const token = getAccessToken();
  const [ok, setOk] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!token) {
      setLoading(false);
      return;
    }
    authMe()
      .then(() => setOk(true))
      .catch(() => {
        clearAccessToken();
        nav("/", { replace: true });
      })
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (!token) return <Navigate to="/" replace />;

  if (loading) {
    return (
      <div className="min-h-screen bg-black text-white flex items-center justify-center text-zinc-400">
        Checking session…
      </div>
    );
  }

  return ok ? children : <Navigate to="/" replace />;
}
