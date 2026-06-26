import type { Metadata } from "next";
import type { ReactNode } from "react";

import { ReactiveCursor } from "@/components/ReactiveCursor";
import { QueryProvider } from "@/providers/QueryProvider";
import "./globals.css";

export const metadata: Metadata = {
  title: "Student Claw — AI project agent for student teams",
  description:
    "A multi-mode AI group agent for Telegram + web. Track projects, deadlines, expenses and more — powered by Agnes AI.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="bg-slate-950 text-slate-200">
        <ReactiveCursor />
        <QueryProvider>{children}</QueryProvider>
      </body>
    </html>
  );
}
