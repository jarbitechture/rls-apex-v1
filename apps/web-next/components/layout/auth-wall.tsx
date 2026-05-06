"use client";

import { Lock } from "lucide-react";

export function AuthWall() {
  return (
    <div className="grid h-screen w-full place-items-center bg-background">
      <div className="max-w-md rounded-xl border bg-card p-8 text-center shadow-sm">
        <div className="mx-auto mb-3 grid h-11 w-11 place-items-center rounded-full bg-destructive/15 text-destructive">
          <Lock className="h-5 w-5" />
        </div>
        <h1 className="font-serif text-xl font-semibold">Access denied</h1>
        <p className="mt-2 text-sm leading-6 text-muted-foreground">
          This account is not on the RLS Apex v1 allowlist. Contact the IT/Legal owner if you should have access.
        </p>
        <p className="mt-4 font-mono text-[11px] text-muted-foreground">
          RLS_ALLOWLIST gate · /api/me 403
        </p>
      </div>
    </div>
  );
}
