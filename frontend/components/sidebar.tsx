"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { useWorkflow } from "@/lib/workflow";

type StepStatus = "complete" | "next" | "locked" | "none";

export function Sidebar() {
  const pathname = usePathname();
  const { institution, researcherCount, scoreCount, assertionCount } = useWorkflow();

  const hasInstitution = !!institution;
  const hasResearchers = researcherCount > 0;
  const hasScores = scoreCount > 0;
  const hasAssertions = assertionCount > 0;

  const workflowItems: Array<{
    href: string;
    label: string;
    status: StepStatus;
  }> = [
    {
      href: "/setup",
      label: "Institution Setup",
      status: hasInstitution ? "complete" : "next",
    },
    {
      href: "/researchers",
      label: "Researchers",
      status: hasResearchers
        ? "complete"
        : hasInstitution
        ? "next"
        : "locked",
    },
    {
      href: "/articles",
      label: "Articles",
      status: hasResearchers ? "none" : "locked",
    },
    {
      href: "/pipeline",
      label: "Run Pipeline",
      status: hasScores
        ? "complete"
        : hasResearchers
        ? "next"
        : "locked",
    },
    {
      href: "/results",
      label: "Results",
      status: hasScores ? "complete" : "locked",
    },
    {
      href: "/stats",
      label: "Statistics",
      status: hasAssertions ? "next" : "locked",
    },
  ];

  const statusIcon: Record<StepStatus, string | null> = {
    complete: "\u2713",
    next: "\u25CF",
    locked: "\u2014",
    none: null,
  };

  const statusColor: Record<StepStatus, string> = {
    complete: "text-green-400",
    next: "text-[#cf4520]",
    locked: "text-gray-600",
    none: "",
  };

  return (
    <aside className="w-52 min-h-full bg-[#34495e] flex flex-col">
      <div className="px-4 pt-4 pb-2">
        <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider">
          Overview
        </p>
      </div>
      <nav className="flex flex-col gap-0.5 px-2 mb-4">
        <Link
          href="/"
          className={cn(
            "px-3 py-2 rounded text-sm transition-colors",
            pathname === "/"
              ? "bg-[#2c3e50] text-white font-medium"
              : "text-gray-300 hover:text-white hover:bg-[#2c3e50]/60"
          )}
        >
          Dashboard
        </Link>
      </nav>

      <div className="px-4 pb-2">
        <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider">
          Workflow
        </p>
      </div>
      <nav className="flex flex-col gap-0.5 px-2 mb-4">
        {workflowItems.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className={cn(
              "px-3 py-2 rounded text-sm transition-colors flex items-center justify-between",
              pathname === item.href
                ? "bg-[#2c3e50] text-white font-medium"
                : item.status === "locked"
                ? "text-gray-500 hover:bg-[#2c3e50]/30"
                : "text-gray-300 hover:text-white hover:bg-[#2c3e50]/60"
            )}
          >
            <span>{item.label}</span>
            {statusIcon[item.status] && (
              <span className={`text-xs ${statusColor[item.status]}`}>
                {statusIcon[item.status]}
              </span>
            )}
          </Link>
        ))}
      </nav>

      <div className="px-4 pb-2">
        <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider">
          Help
        </p>
      </div>
      <nav className="flex flex-col gap-0.5 px-2">
        <Link
          href="/faq"
          className={cn(
            "px-3 py-2 rounded text-sm transition-colors",
            pathname === "/faq"
              ? "bg-[#2c3e50] text-white font-medium"
              : "text-gray-300 hover:text-white hover:bg-[#2c3e50]/60"
          )}
        >
          FAQ
        </Link>
      </nav>
    </aside>
  );
}
