"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Plus, Bot, Folder } from "lucide-react";
import { cn } from "@/lib/utils";
import type { Me } from "@/lib/rls-api";

type NavItem = { label: string; href: string; icon: React.ComponentType<{ className?: string }> };

const NAV: NavItem[] = [
  { label: "Validate",  href: "/validate",  icon: Bot },
  { label: "Documents", href: "/documents", icon: Folder },
];

export function Sidebar({ user }: { user: Me | null }) {
  const pathname = usePathname() || "/";
  return (
    <aside className="flex w-60 shrink-0 flex-col border-r bg-sidebar text-sidebar-foreground">
      {/* Org plate (display-only, no dropdown) */}
      <div className="flex items-center gap-3 px-4 py-3">
        <div className="grid h-7 w-7 place-items-center rounded-md bg-gradient-to-br from-primary to-primary/70 text-[11px] font-bold tracking-wider text-primary-foreground shadow-inner">
          MC
        </div>
        <div className="flex min-w-0 flex-col leading-tight">
          <span className="truncate text-[13px] font-semibold">Manatee County</span>
          <span className="text-[11px] text-muted-foreground">RLS Apex · v0.1.0</span>
        </div>
      </div>

      {/* Primary CTA — routes to Validate (the pilot's flow) */}
      <div className="px-3 pb-3">
        <Link
          href="/validate"
          className="flex h-9 items-center justify-center gap-2 rounded-md bg-primary text-[13px] font-semibold text-primary-foreground shadow-sm transition hover:bg-primary/90"
        >
          <Plus className="h-3.5 w-3.5" /> Validate a draft
        </Link>
      </div>

      {/* Nav */}
      <nav className="flex flex-1 flex-col gap-0.5 px-2">
        {NAV.map(({ label, href, icon: Icon }) => {
          const active = pathname === href || pathname.startsWith(href + "/");
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex h-8 items-center gap-2 rounded-md px-2.5 text-[13px] transition",
                active
                  ? "bg-sidebar-accent font-semibold text-sidebar-accent-foreground"
                  : "text-sidebar-foreground/80 hover:bg-sidebar-accent/50",
              )}
            >
              <Icon className="h-3.5 w-3.5" />
              {label}
            </Link>
          );
        })}
      </nav>

      {/* Footer — live user from /api/me */}
      <div className="mt-auto flex items-center gap-2.5 border-t px-4 py-3">
        <div className="grid h-7 w-7 place-items-center rounded-full bg-gradient-to-br from-amber-700 to-amber-500 text-[11px] font-semibold text-white">
          {user?.initials ?? "RP"}
        </div>
        <div className="flex min-w-0 flex-col leading-tight">
          <span className="truncate text-[12.5px] font-semibold">{user?.display_name ?? "RLS Pilot"}</span>
          <span className="truncate text-[10.5px] text-muted-foreground">{user?.role ?? "v0.1.0 · mock"}</span>
        </div>
      </div>
    </aside>
  );
}
