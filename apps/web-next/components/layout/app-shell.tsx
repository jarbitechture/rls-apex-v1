"use client";

import { useEffect, useState } from "react";
import { RLS_API, APIError, type Me } from "@/lib/rls-api";
import { Sidebar } from "./sidebar";
import { AuthWall } from "./auth-wall";
import { Skeleton } from "@/components/ui/skeleton";

type AuthState = "loading" | "allowed" | "denied" | "offline";

export function AppShell({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<Me | null>(null);
  const [auth, setAuth] = useState<AuthState>("loading");

  useEffect(() => {
    RLS_API.me()
      .then((u) => { setUser(u); setAuth("allowed"); })
      .catch((e) => {
        if (e instanceof APIError && e.status === 403) setAuth("denied");
        else setAuth("offline");
      });
  }, []);

  if (auth === "denied") return <AuthWall />;

  // 'loading' and 'offline' both render the shell — offline means Pages
  // (no gateway) where the static demo should still be visible.
  return (
    <div className="flex h-screen w-full bg-background">
      <Sidebar user={user} />
      <main className="flex flex-1 flex-col overflow-hidden">
        {auth === "loading" ? (
          <div className="flex flex-col gap-4 p-8">
            <Skeleton className="h-8 w-48" />
            <Skeleton className="h-4 w-96" />
            <Skeleton className="mt-4 h-32 w-full max-w-3xl" />
          </div>
        ) : (
          children
        )}
      </main>
    </div>
  );
}
