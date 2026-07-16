"use client";

import { Card, CardContent, CardHeader } from "@/components/ui/card";

function Skeleton({ className = "" }: { className?: string }) {
  return (
    <div className={`animate-pulse bg-muted rounded ${className}`} />
  );
}

export function MessageSkeleton() {
  return (
    <div className="space-y-4 p-4">
      {[...Array(3)].map((_, i) => (
        <div key={i} className={`flex ${i % 2 === 0 ? "justify-end" : "justify-start"}`}>
          <div className={`max-w-[70%] space-y-2 ${i % 2 === 0 ? "items-end" : "items-start"}`}>
            <Skeleton className="h-4 w-48" />
            <Skeleton className="h-4 w-36" />
            {i % 2 !== 0 && <Skeleton className="h-4 w-56" />}
          </div>
        </div>
      ))}
    </div>
  );
}

export function DashboardSkeleton() {
  return (
    <div className="p-6 space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {[...Array(3)].map((_, i) => (
          <Card key={i}>
            <CardHeader className="pb-2">
              <Skeleton className="h-4 w-24" />
            </CardHeader>
            <CardContent>
              <div className="flex flex-col items-center py-4 space-y-3">
                <Skeleton className="h-28 w-28 rounded-full" />
                <Skeleton className="h-3 w-20" />
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
      <Card>
        <CardHeader className="pb-2">
          <Skeleton className="h-4 w-32" />
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-2">
            {[...Array(12)].map((_, i) => (
              <Skeleton key={i} className="h-8 w-24" />
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

export function ConceptGraphSkeleton() {
  return (
    <div className="flex items-center justify-center h-full">
      <div className="space-y-4 text-center">
        <Skeleton className="h-48 w-64 mx-auto" />
        <Skeleton className="h-4 w-32 mx-auto" />
      </div>
    </div>
  );
}

export { Skeleton };
