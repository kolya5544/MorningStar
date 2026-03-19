import React, { useEffect, useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { authMe, clearAccessToken, getAccessToken, type Role } from "@/Api";

export function RequireAuth({
  children,
  allowedRoles,
}: {
  children: JSX.Element;
  allowedRoles?: Role[];
}) {
  const nav = useNavigate();
  const token = getAccessToken();
  const [ok, setOk] = useState(false);
  const [loading, setLoading] = useState(true);
  const [forbidden, setForbidden] = useState(false);

  useEffect(() => {
    if (!token) {
      setLoading(false);
      return;
    }

    authMe()
      .then((me) => {
        if (allowedRoles && !allowedRoles.includes(me.role)) {
          setForbidden(true);
          setOk(false);
          return;
        }
        setOk(true);
      })
      .catch(() => {
        clearAccessToken();
        nav("/", { replace: true });
      })
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (!token) return <Navigate to="/" replace />;
  if (forbidden) return <Navigate to="/dashboard" replace />;

  if (loading) {
    return (
      <div className="min-h-screen bg-black text-white flex items-center justify-center text-zinc-400">
        Checking session...
      </div>
    );
  }

  return ok ? children : <Navigate to="/" replace />;
}
