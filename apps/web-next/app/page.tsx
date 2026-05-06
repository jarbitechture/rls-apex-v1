// Root route — redirects to /validate (the pilot's entry surface).
// Static export can't use server redirects; client-side does the job.
"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function Home() {
  const router = useRouter();
  useEffect(() => { router.replace("/validate"); }, [router]);
  return null;
}
