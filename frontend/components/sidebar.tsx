"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { href: "/", label: "Dashboard" },
  { href: "/setup", label: "Institution Setup" },
  { href: "/researchers", label: "Researchers" },
  { href: "/articles", label: "Articles" },
  { href: "/pipeline", label: "Pipeline" },
  { href: "/results", label: "Results" },
  { href: "/faq", label: "FAQ" },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="w-52 min-h-full bg-[#34495e] flex flex-col">
      <div className="px-4 pt-4 pb-2">
        <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider">
          Navigation
        </p>
      </div>
      <nav className="flex flex-col gap-0.5 px-2">
        {NAV_ITEMS.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className={cn(
              "px-3 py-2 rounded text-sm transition-colors",
              pathname === item.href
                ? "bg-[#2c3e50] text-white font-medium"
                : "text-gray-300 hover:text-white hover:bg-[#2c3e50]/60"
            )}
          >
            {item.label}
          </Link>
        ))}
      </nav>
    </aside>
  );
}
