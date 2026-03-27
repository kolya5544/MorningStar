import { Link } from "react-router-dom";

import { useSeo } from "@/lib/seo";

export default function NotFound() {
  useSeo({
    title: "Page not found | MorningStar",
    description: "The requested MorningStar page does not exist.",
    canonicalPath: "/404",
    robots: "noindex,nofollow",
  });

  return (
    <main className="flex min-h-screen items-center justify-center bg-black px-4 text-white">
      <section className="w-full max-w-xl rounded-3xl border border-white/10 bg-zinc-950/70 p-8 text-center">
        <p className="text-sm uppercase tracking-[0.25em] text-zinc-500">404</p>
        <h1 className="mt-3 text-3xl font-semibold">Page not found</h1>
        <p className="mt-3 text-zinc-400">
          MorningStar could not find this route. Public indexing is limited to the landing page.
        </p>
        <Link
          to="/"
          className="mt-6 inline-flex rounded-xl border border-white/10 px-4 py-2 text-sm text-white transition hover:bg-white/5"
        >
          Go to landing page
        </Link>
      </section>
    </main>
  );
}
