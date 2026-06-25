/**
 * Authenticated dashboard layout (blueprint §6.1).
 *
 * Server component that establishes the sidebar + content shell and wraps the
 * subtree in the SSEProvider so every dashboard page shares one real-time
 * stream. The access JWT is read server-side to greet the user; the middleware
 * has already guaranteed a valid session before this renders.
 */

import { redirect } from "next/navigation";
import type { ReactNode } from "react";

import { Sidebar } from "@/components/Sidebar";
import { Topbar } from "@/components/Topbar";
import { getSession } from "@/lib/auth";
import { SSEProvider } from "@/providers/SSEProvider";

export default async function DashboardLayout({
  children,
}: {
  children: ReactNode;
}) {
  const auth = await getSession();
  // Defense in depth: the middleware guards most paths, but the dashboard root
  // ("/") isn't in its matcher, so enforce auth here too.
  if (!auth) redirect("/login");
  const username = auth.session.username;

  return (
    <SSEProvider>
      <div className="flex h-screen overflow-hidden">
        <Sidebar username={username} />
        <div className="flex min-w-0 flex-1 flex-col">
          <Topbar />
          <main className="flex-1 overflow-y-auto bg-slate-50">{children}</main>
        </div>
      </div>
    </SSEProvider>
  );
}
