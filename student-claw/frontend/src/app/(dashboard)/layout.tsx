/**
 * Authenticated dashboard layout (blueprint §6.1).
 *
 * Server component that establishes the sidebar + content shell and wraps the
 * subtree in the SSEProvider so every dashboard page shares one real-time
 * stream. The access JWT is read server-side to greet the user; the middleware
 * has already guaranteed a valid session before this renders.
 */

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
  const username = auth?.session.username ?? "You";

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
