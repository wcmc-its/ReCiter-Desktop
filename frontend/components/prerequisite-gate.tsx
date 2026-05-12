"use client";

import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

interface PrerequisiteGateProps {
  met: boolean;
  message: string;
  actionLabel: string;
  actionHref: string;
  children: React.ReactNode;
}

export function PrerequisiteGate({
  met,
  message,
  actionLabel,
  actionHref,
  children,
}: PrerequisiteGateProps) {
  if (met) return <>{children}</>;

  return (
    <Card className="border-amber-200 bg-amber-50 shadow-sm max-w-lg">
      <CardContent className="p-6 text-center">
        <p className="text-sm text-amber-800 mb-3">{message}</p>
        <Link href={actionHref}>
          <Button
            variant="outline"
            className="border-amber-300 text-amber-700 hover:bg-amber-100"
          >
            {actionLabel}
          </Button>
        </Link>
      </CardContent>
    </Card>
  );
}
