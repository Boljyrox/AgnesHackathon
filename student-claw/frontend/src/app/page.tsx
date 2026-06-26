"use client";

/**
 * Public landing page — premium dark, Bugatti-inspired. Reactive gradient
 * background, framer-motion reveals, magnetic CTAs, and a 3-step onboarding
 * guide below the fold.
 */

import { motion, useScroll, useTransform, type Variants } from "framer-motion";
import Link from "next/link";
import { useRef } from "react";

import { SiteNav } from "@/components/marketing/SiteNav";

const reveal: Variants = {
  hidden: { opacity: 0, y: 24 },
  show: (i = 0) => ({
    opacity: 1,
    y: 0,
    transition: { duration: 0.6, delay: i * 0.08, ease: "easeOut" },
  }),
};

const STEPS = [
  {
    n: "01",
    title: "Add to Telegram",
    body: "Drop @sutdclaw_bot into your project group chat. It auto-registers and hands you a Project Key.",
    icon: "💬",
  },
  {
    n: "02",
    title: "Type /sc",
    body: "One command opens the whole app — summaries, deadlines, expenses, roles. No syntax to memorise.",
    icon: "⌘",
  },
  {
    n: "03",
    title: "Authenticate with /verify",
    body: "Link your web account with the token from the dashboard. Your projects, deadlines and files appear instantly.",
    icon: "🔑",
  },
];

export default function LandingPage() {
  const heroRef = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({ target: heroRef, offset: ["start start", "end start"] });
  const yBlob = useTransform(scrollYProgress, [0, 1], [0, 160]);
  const fade = useTransform(scrollYProgress, [0, 1], [1, 0]);

  return (
    <main className="relative min-h-screen overflow-hidden bg-slate-950 text-slate-200">
      {/* Reactive background */}
      <div className="pointer-events-none absolute inset-0 -z-10">
        <div className="absolute inset-0 bg-grid-faint [background-size:44px_44px]" />
        <motion.div
          style={{ y: yBlob }}
          className="absolute -left-40 top-[-10%] h-[36rem] w-[36rem] rounded-full bg-brand-500/20 blur-[120px] animate-pulse-glow"
        />
        <motion.div
          style={{ y: yBlob }}
          className="absolute right-[-15%] top-[20%] h-[34rem] w-[34rem] rounded-full bg-fuchsia-500/10 blur-[120px] animate-pulse-glow"
        />
        <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-brand-500/40 to-transparent" />
      </div>

      <SiteNav />

      {/* Hero */}
      <section ref={heroRef} className="relative mx-auto flex max-w-6xl flex-col items-center px-5 pb-24 pt-40 text-center">
        <motion.span
          variants={reveal}
          initial="hidden"
          animate="show"
          className="mb-6 inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-4 py-1.5 text-xs text-brand-300 backdrop-blur"
        >
          <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-brand-400" />
          Multi-mode AI group agent · powered by Agnes AI
        </motion.span>

        <motion.h1
          variants={reveal}
          custom={1}
          initial="hidden"
          animate="show"
          className="max-w-4xl bg-gradient-to-b from-white to-slate-400 bg-clip-text text-5xl font-semibold leading-[1.05] tracking-tight text-transparent sm:text-7xl"
        >
          Your group chat,
          <br />
          <span className="bg-gradient-to-r from-brand-300 to-brand-500 bg-clip-text text-transparent">
            running itself.
          </span>
        </motion.h1>

        <motion.p
          variants={reveal}
          custom={2}
          initial="hidden"
          animate="show"
          className="mt-6 max-w-xl text-lg text-slate-400"
        >
          Student Claw turns a Telegram group into a smart project agent — extracting
          deadlines, delegating tasks, reading your PDFs, and tracking expenses, all
          from one command.
        </motion.p>

        <motion.div
          variants={reveal}
          custom={3}
          initial="hidden"
          animate="show"
          className="mt-10 flex flex-col items-center gap-4 sm:flex-row"
        >
          <Link
            href="/register"
            data-magnetic
            className="group relative overflow-hidden rounded-2xl bg-brand-500 px-10 py-5 text-lg font-semibold text-white shadow-glow-lg transition-transform hover:scale-[1.03]"
          >
            <span className="relative z-10">Get Started →</span>
            <span className="absolute inset-0 -translate-x-full bg-gradient-to-r from-transparent via-white/30 to-transparent transition-transform duration-700 group-hover:translate-x-full" />
          </Link>
          <Link
            href="/docs"
            data-magnetic
            className="rounded-2xl border border-white/10 px-8 py-5 text-lg font-medium text-slate-200 backdrop-blur transition-colors hover:bg-white/5"
          >
            Read the docs
          </Link>
        </motion.div>

        {/* Placeholder product image blocks */}
        <motion.div style={{ opacity: fade }} className="mt-20 w-full max-w-5xl">
          <div className="relative rounded-3xl border border-white/10 bg-white/[0.03] p-3 shadow-glow backdrop-blur-xl">
            <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
              {["Kanban", "Ask Agnes", "Deadlines"].map((label, i) => (
                <div
                  key={label}
                  className="group relative aspect-[4/3] overflow-hidden rounded-2xl border border-white/10 bg-gradient-to-br from-slate-800/60 to-slate-900/60"
                  style={{ animationDelay: `${i * 0.4}s` }}
                >
                  <div className="absolute inset-0 animate-float bg-[radial-gradient(circle_at_30%_20%,rgba(56,189,248,0.15),transparent_60%)]" />
                  <span className="absolute bottom-4 left-4 text-sm font-medium text-slate-300">
                    {label}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </motion.div>
      </section>

      {/* Onboarding guide */}
      <section className="relative mx-auto max-w-6xl px-5 py-24">
        <motion.h2
          variants={reveal}
          initial="hidden"
          whileInView="show"
          viewport={{ once: true }}
          className="text-center text-3xl font-semibold tracking-tight text-white sm:text-4xl"
        >
          Up and running in three steps
        </motion.h2>
        <p className="mx-auto mt-3 max-w-md text-center text-slate-400">
          No setup, no config files. Add the bot and go.
        </p>

        <div className="mt-14 grid gap-5 md:grid-cols-3">
          {STEPS.map((s, i) => (
            <motion.div
              key={s.n}
              variants={reveal}
              custom={i}
              initial="hidden"
              whileInView="show"
              viewport={{ once: true }}
              data-magnetic
              className="group relative overflow-hidden rounded-2xl border border-white/10 bg-white/[0.03] p-7 backdrop-blur-xl transition-colors hover:border-brand-500/40"
            >
              <div className="absolute -right-6 -top-8 text-8xl font-bold text-white/[0.04]">
                {s.n}
              </div>
              <div className="mb-4 grid h-12 w-12 place-items-center rounded-xl bg-brand-500/15 text-2xl">
                {s.icon}
              </div>
              <h3 className="text-lg font-semibold text-white">{s.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-slate-400">{s.body}</p>
            </motion.div>
          ))}
        </div>

        <div className="mt-16 text-center">
          <Link
            href="/register"
            data-magnetic
            className="inline-flex rounded-2xl bg-brand-500 px-8 py-4 font-semibold text-white shadow-glow transition-transform hover:scale-[1.03]"
          >
            Create your account
          </Link>
        </div>
      </section>

      <footer className="border-t border-white/10 py-10 text-center text-sm text-slate-500">
        <div className="mx-auto flex max-w-6xl flex-col items-center gap-2 px-5">
          <img src="/logo.svg" alt="" className="h-6 w-6 rounded" />
          <p>Student Claw — built for student teams. Powered by Agnes AI &amp; Qwen-VL.</p>
          <div className="flex gap-4">
            <Link href="/docs" className="hover:text-slate-300">Docs</Link>
            <Link href="/login" className="hover:text-slate-300">Sign in</Link>
          </div>
        </div>
      </footer>
    </main>
  );
}
