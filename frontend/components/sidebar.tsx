"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { useWorkflow } from "@/lib/workflow";

type StepStatus = "complete" | "next" | "locked" | "none" | "running";

export function Sidebar() {
  const pathname = usePathname();
  const { institution, researcherCount, articleCount, uploadedArticles, scoreCount, pipelineRunning } = useWorkflow();

  const hasInstitution = !!institution;
  const hasResearchers = researcherCount > 0;
  const hasArticles = articleCount > 0;
  const hasScores = scoreCount > 0;

  function compactNum(n: number): string {
    if (n >= 1000) return `${Math.round(n / 1000)}k`;
    return String(n);
  }

  const articleSubtitle = hasArticles && uploadedArticles > 0
    ? `${compactNum(uploadedArticles)} uploaded`
    : null;

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
      label: "Known Articles",
      status: hasArticles ? "complete" : hasResearchers ? "next" : "locked",
    },
    {
      href: "/pipeline",
      label: "Retrieve & Score",
      status: pipelineRunning
        ? "running" as StepStatus
        : hasScores
        ? "complete"
        : hasArticles
        ? "next"
        : "locked",
    },
    {
      href: "/results",
      label: "Results",
      status: hasScores ? "complete" : "locked",
    },
  ];

  const statusIcon: Record<StepStatus, string | null> = {
    complete: "\u2713",
    running: "\u25CF",
    next: "\u25CF",
    locked: "\u2014",
    none: null,
  };

  const statusColor: Record<StepStatus, string> = {
    complete: "text-green-400",
    running: "text-blue-400 animate-pulse",
    next: "text-[#e05a5a]",
    locked: "text-[#a8b4cc]/30",
    none: "",
  };

  const sectionLabel = "text-[10px] font-semibold uppercase tracking-[0.1em] text-[#a8b4cc]/40 px-5 pb-1.5";

  const linkBase = "px-5 py-[9px] text-[13px] transition-[background,color] duration-150 flex items-center justify-between border-l-2";
  const linkActive = "bg-[#2d3a52] text-white font-medium border-l-[#e05a5a]";
  const linkDefault = "text-[#a8b4cc] hover:text-white hover:bg-[#242e44] border-l-transparent";
  const linkLocked = "text-[#a8b4cc]/40 hover:bg-[#242e44]/50 border-l-transparent";

  return (
    <aside className="w-[220px] min-h-full bg-[#1a2133] flex flex-col pt-4">
      <div className="mb-4">
        <p className={sectionLabel}>Overview</p>
        <nav className="flex flex-col">
          <Link
            href="/"
            className={cn(linkBase, pathname === "/" ? linkActive : linkDefault)}
          >
            Dashboard
          </Link>
        </nav>
      </div>

      <div className="mb-4">
        <p className={sectionLabel}>Workflow</p>
        <nav className="flex flex-col">
          {workflowItems.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                linkBase,
                pathname === item.href
                  ? linkActive
                  : item.status === "locked"
                  ? linkLocked
                  : linkDefault
              )}
            >
              <span className="flex flex-col">
                <span>{item.label}</span>
                {item.href === "/articles" && articleSubtitle && (
                  <span className="text-[10px] text-[#a8b4cc]/40 leading-tight">{articleSubtitle}</span>
                )}
              </span>
              {statusIcon[item.status] && (
                <span className={`text-xs ${statusColor[item.status]}`}>
                  {statusIcon[item.status]}
                </span>
              )}
            </Link>
          ))}
        </nav>
      </div>

      {hasScores && (
        <div className="mb-4">
          <p className={sectionLabel}>Analysis</p>
          <nav className="flex flex-col">
            <Link
              href="/stats"
              className={cn(linkBase, pathname === "/stats" ? linkActive : linkDefault)}
            >
              Statistics
            </Link>
            <Link
              href="/orcid"
              className={cn(linkBase, pathname === "/orcid" ? linkActive : linkDefault)}
            >
              ORCID Inference
            </Link>
          </nav>
        </div>
      )}

      <div className="mt-auto mb-4 border-t border-[#2a3350] pt-4">
        <p className={sectionLabel}>Help</p>
        <nav className="flex flex-col">
          <Link
            href="/faq"
            className={cn(linkBase, pathname === "/faq" ? linkActive : linkDefault)}
          >
            FAQ
          </Link>
        </nav>
      </div>
    </aside>
  );
}
