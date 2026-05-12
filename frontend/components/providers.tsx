"use client";

import { WorkflowProvider } from "@/lib/workflow";
import { PipelineProvider } from "@/lib/pipeline-context";

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <WorkflowProvider>
      <PipelineProvider>{children}</PipelineProvider>
    </WorkflowProvider>
  );
}
