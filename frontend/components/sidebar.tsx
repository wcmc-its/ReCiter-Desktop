"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { href: "/", label: "Dashboard", icon: "\u2302" },
  { href: "/setup", label: "Institution Setup", icon: "\u2616" },
  { href: "/researchers", label: "Researchers", icon: "\u263B" },
  { href: "/articles", label: "Articles", icon: "\u2637" },
  { href: "/pipeline", label: "Pipeline", icon: "\u2248" },
  { href: "/results", label: "Results", icon: "\u2261" },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="w-56 min-h-screen bg-gray-950 border-r border-gray-800 p-4 flex flex-col">
      <div className="mb-8">
        <h1 className="text-lg font-semibold text-white">ReCiter Desktop</h1>
        <p className="text-xs text-gray-500 mt-1">Author Disambiguation</p>
      </div>
      <nav className="flex flex-col gap-1">
        {NAV_ITEMS.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className={cn(
              "flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors",
              pathname === item.href
                ? "bg-gray-800 text-white"
                : "text-gray-400 hover:text-white hover:bg-gray-900"
            )}
          >
            <span className="text-base">{item.icon}</span>
            {item.label}
          </Link>
        ))}
      </nav>
    </aside>
  );
}
