import * as React from "react";

export function Input(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      {...props}
      className={
        "w-full rounded-xl bg-zinc-900 border border-white/10 px-3 py-2 text-sm text-white " +
        "placeholder:text-zinc-500 focus:outline-none focus:ring-2 focus:ring-[#16335f] " +
        (props.className ?? "")
      }
    />
  );
}
