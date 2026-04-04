"use client";

import { useWorkflow } from "@/lib/workflow";
import { PrerequisiteGate } from "@/components/prerequisite-gate";
import { Card, CardContent } from "@/components/ui/card";

export default function StatsPage() {
  const { assertionCount } = useWorkflow();

  return (
    <PrerequisiteGate
      met={assertionCount > 0}
      message="Statistics require scored articles with accepted or rejected decisions. Run the pipeline and import assertions first."
      actionLabel="Go to Pipeline"
      actionHref="/pipeline"
    >
      <div className="max-w-4xl">
        <h2 className="text-2xl font-semibold mb-2 text-gray-900">Statistics</h2>
        <p className="text-gray-500 text-sm mb-6">
          Scoring quality metrics for your pipeline run.
        </p>
        <Card className="border-gray-200 bg-white shadow-sm">
          <CardContent className="p-5 text-center">
            <p className="text-sm text-gray-500 py-8">
              Charts are coming in Phase 3. Your stats data is ready.
            </p>
          </CardContent>
        </Card>
      </div>
    </PrerequisiteGate>
  );
}
