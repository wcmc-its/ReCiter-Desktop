"use client";

import { WorkflowProvider } from "@/lib/workflow";

export function Providers({ children }: { children: React.ReactNode }) {
  return <WorkflowProvider>{children}</WorkflowProvider>;
}
