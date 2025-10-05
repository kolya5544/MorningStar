import React, { JSX } from "react";
import { Button } from "@/components/ui/button";
import { LogIn, UserPlus } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Input } from "@/components/ui/input";
import { Modal } from "@/components/ui/modal";

/**
 * MorningStar Landing Page
 * - Single-screen static hero
 * - Dark theme with deep blue accents
 * - Header with brand and auth actions
 * - Centered headline and primary CTAs
 */
export default function Landing(): JSX.Element {
  const [openSignUp, setOpenSignUp] = useState(false);
  const [openLogin, setOpenLogin] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const nav = useNavigate();

  return (
    <div className="min-h-screen bg-black text-white relative">
      {/* BG image */}
      <div
        aria-hidden
        className="absolute inset-0 z-0 bg-center bg-cover"
        style={{ backgroundImage: "url('/bg.jpg')" }}
      />
      {/* Dark overlay */}
      <div className="absolute inset-0 z-10 bg-black/70" />

      {/* Content above overlay */}
      <div className="relative z-20">
        {/* Header */}
        <header className="sticky top-0 z-20 w-full">
          <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
            <div className="flex h-16 items-center justify-between">
              {/* Brand */}
              <div className="flex items-center gap-3">
                <img
                  src="/morningstar.svg"
                  alt="MorningStar"
                  className="h-8 w-8 shrink-0 align-middle"
                />
                <span className="text-lg font-semibold tracking-wide">MorningStar</span>
              </div>

              {/* Actions */}
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
          {/* subtle divider */}
          <div className="h-px w-full bg-gradient-to-r from-transparent via-[#16335f] to-transparent opacity-50" />
        </header>

        {/* Hero */}
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
        {/* Sign Up modal */}
        <Modal
          open={openSignUp}
          onClose={() => {
            setOpenSignUp(false);
            setEmail("");
          }}
          title="Create your account"
          onPrimary={() => {
            //setOpenSignUp(false);
            nav("/dashboard");
          }}
          primaryLabel="Continue"
        >
          <label className="block text-sm text-zinc-300">Email</label>
          <Input
            type="email"
            placeholder="you@example.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </Modal>

        {/* Log In modal */}
        <Modal
          open={openLogin}
          onClose={() => {
            setOpenLogin(false);
            setEmail("");
            setPassword("");
          }}
          title="Log in"
          onPrimary={() => {
            //setOpenLogin(false);
            nav("/dashboard");
          }}
          primaryLabel="Continue"
        >
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
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </div>
          </div>
        </Modal>
      </div>

      {/* Footer spacing for full-screen aesthetics */}
      <div className="pb-10" />
    </div>
  );
}
