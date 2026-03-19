import { apiHealth, authRegister } from "@/Api";
import { useAuth } from "@/auth/AuthProvider";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Modal } from "@/components/ui/modal";
import { LogIn, UserPlus } from "lucide-react";
import { useEffect, useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";

export default function Landing() {
  const { isAuthenticated, signIn } = useAuth();
  const [openSignUp, setOpenSignUp] = useState(false);
  const [openLogin, setOpenLogin] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [apiOk, setApiOk] = useState<boolean | null>(null);
  const [signUpBusy, setSignUpBusy] = useState(false);
  const [signUpErr, setSignUpErr] = useState<string | null>(null);
  const [loginBusy, setLoginBusy] = useState(false);
  const [loginErr, setLoginErr] = useState<string | null>(null);
  const [loginHint, setLoginHint] = useState<string | null>(null);
  const nav = useNavigate();

  useEffect(() => {
    let stop = false;
    (async () => {
      try {
        const health = await apiHealth();
        if (!stop) setApiOk(health?.status?.toLowerCase?.() === "ok");
      } catch {
        if (!stop) setApiOk(false);
      }
    })();
    return () => {
      stop = true;
    };
  }, []);

  if (isAuthenticated) {
    return <Navigate to="/dashboard" replace />;
  }

  return (
    <div className="min-h-screen bg-black text-white relative">
      <div
        aria-hidden
        className="absolute inset-0 z-0 bg-center bg-cover"
        style={{ backgroundImage: "url('/bg.jpg')" }}
      />
      <div className="absolute inset-0 z-10 bg-black/70" />

      <div className="relative z-20">
        <header className="sticky top-0 z-20 w-full">
          <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
            <div className="flex h-16 items-center justify-between">
              <div className="flex items-center gap-3">
                <img
                  src="/morningstar.svg"
                  alt="MorningStar"
                  className="h-8 w-8 shrink-0 align-middle"
                />
                <span className="text-lg font-semibold tracking-wide">MorningStar</span>
                <span
                  title={apiOk === null ? "Checking API..." : apiOk ? "API OK" : "API DOWN"}
                  className={`ml-3 inline-flex items-center gap-2 text-xs ${
                    apiOk === null ? "text-zinc-400" : apiOk ? "text-emerald-400" : "text-red-400"
                  }`}
                >
                  <span
                    className={`inline-block h-2 w-2 rounded-full ${
                      apiOk === null ? "bg-zinc-500" : apiOk ? "bg-emerald-400" : "bg-red-400"
                    }`}
                  />
                  {apiOk === null ? "checking" : apiOk ? "api ok" : "api down"}
                </span>
              </div>

              <nav className="flex items-center gap-2">
                <Button
                  variant="ghost"
                  onClick={() => setOpenLogin(true)}
                  className="text-sm text-zinc-200 hover:text-white hover:bg-white/5"
                >
                  <LogIn className="mr-2 h-4 w-4" /> Log In
                </Button>
                <Button
                  onClick={() => setOpenSignUp(true)}
                  className="text-sm bg-[#0b1f3a] hover:bg-[#0e2a54] border border-[#16335f]"
                >
                  <UserPlus className="mr-2 h-4 w-4" /> Sign Up
                </Button>
              </nav>
            </div>
          </div>
          <div className="h-px w-full bg-gradient-to-r from-transparent via-[#16335f] to-transparent opacity-50" />
        </header>

        <main className="mx-auto flex max-w-7xl flex-col items-center px-4 py-24 sm:py-32 text-center">
          <h1 className="text-4xl font-bold sm:text-5xl md:text-6xl">Plan your future ahead!</h1>
          <p className="mt-4 max-w-2xl text-base sm:text-lg text-zinc-300">
            Track crypto portfolios, import wallets, and see your performance at a glance.
          </p>

          <div className="mt-8 flex flex-col sm:flex-row items-center gap-3">
            <Button
              className="h-11 px-6 text-sm bg-[#0b1f3a] hover:bg-[#0e2a54] border border-[#16335f]"
              onClick={() => setOpenSignUp(true)}
            >
              <UserPlus className="mr-2 h-4 w-4" /> Sign Up
            </Button>
            <Button
              variant="outline"
              className="h-11 px-6 text-sm border-zinc-700/80 bg-white/0 text-white hover:bg-white/5"
              onClick={() => setOpenLogin(true)}
            >
              <LogIn className="mr-2 h-4 w-4" /> Log In
            </Button>
          </div>
        </main>

        <Modal
          open={openSignUp}
          onClose={() => {
            setOpenSignUp(false);
            setEmail("");
          }}
          title="Create your account"
          onPrimary={async () => {
            if (apiOk === false) return alert("API is unavailable");
            const normalizedEmail = email.trim();
            if (!normalizedEmail) return;

            try {
              setSignUpBusy(true);
              setSignUpErr(null);
              await authRegister(normalizedEmail);
              setOpenSignUp(false);
              setLoginHint("Password sent to your email. Use it to log in.");
              setOpenLogin(true);
            } catch (error: unknown) {
              setSignUpErr(error instanceof Error ? error.message : "Failed to sign up");
            } finally {
              setSignUpBusy(false);
            }
          }}
          primaryLabel={signUpBusy ? "Please wait..." : apiOk === false ? "API down" : "Send password"}
        >
          {signUpErr && <div className="text-sm text-red-400">{signUpErr}</div>}
          <label className="block text-sm text-zinc-300">Email</label>
          <Input
            type="email"
            placeholder="you@example.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </Modal>

        <Modal
          open={openLogin}
          onClose={() => {
            setOpenLogin(false);
            setEmail("");
            setPassword("");
          }}
          title="Log in"
          onPrimary={async () => {
            if (apiOk === false) return alert("API is unavailable");
            const normalizedEmail = email.trim();
            if (!normalizedEmail || !password) return;

            try {
              setLoginBusy(true);
              setLoginErr(null);
              await signIn(normalizedEmail, password);
              nav("/dashboard", { replace: true });
            } catch (error: unknown) {
              setLoginErr(error instanceof Error ? error.message : "Failed to log in");
            } finally {
              setLoginBusy(false);
            }
          }}
          primaryLabel={loginBusy ? "Please wait..." : apiOk === false ? "API down" : "Continue"}
        >
          {loginHint && <div className="text-sm text-emerald-400">{loginHint}</div>}
          {loginErr && <div className="text-sm text-red-400">{loginErr}</div>}
          <div className="space-y-3">
            <div>
              <label className="block text-sm text-zinc-300">Email</label>
              <Input
                type="email"
                placeholder="you@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </div>
            <div>
              <label className="block text-sm text-zinc-300">Password</label>
              <Input
                type="password"
                placeholder="********"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </div>
          </div>
        </Modal>
      </div>

      <div className="pb-10" />
    </div>
  );
}
