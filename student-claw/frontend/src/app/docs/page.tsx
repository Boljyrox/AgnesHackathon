/** /docs — how to use the bot, how Agnes processes data, FAQ. */

import Link from "next/link";

import { SiteNav } from "@/components/marketing/SiteNav";

export const metadata = { title: "Docs — Student Claw" };

const COMMANDS: [string, string][] = [
  ["/sc", "Opens the master inline menu — Summary, Assign Work, Goals, Deadlines, Sync, Set, Clear, Activation and more."],
  ["/ask <question>", "Ask Agnes anything about your project — answered from chat history + your uploaded documents."],
  ["/verify <token>", "Link your Telegram identity to your web account using the token from the dashboard."],
];

const FAQ: [string, string][] = [
  ["Is my group's data private?", "Every project is isolated by chat_id with its own vector namespace. Queries can only ever read your group's data — never another team's."],
  ["Can Agnes read PDFs and images?", "Yes. Images and scanned PDFs are read by Qwen-2.5-VL; text PDFs and slide decks are parsed directly. Share a file, run Sync, then ask about it."],
  ["What happens when I deactivate the bot?", "It ignores all messages, files and commands in the group until a group leader re-activates it. Nothing is processed in the meantime."],
  ["Who can change settings?", "Sensitive actions (Clear, Activation, Set Details, Set Roles) are restricted to group Leaders. Members get a friendly 'Leaders only' prompt."],
  ["How do I clear what the bot remembers?", "Set → Clear in the /sc menu wipes the vector memory (your files in storage are kept). It's leader-only and irreversible."],
];

function Section({ id, title, children }: { id: string; title: string; children: React.ReactNode }) {
  return (
    <section id={id} className="scroll-mt-24">
      <h2 className="text-2xl font-semibold tracking-tight text-white">{title}</h2>
      <div className="mt-4 space-y-4 text-slate-400">{children}</div>
    </section>
  );
}

export default function DocsPage() {
  return (
    <main className="relative min-h-screen bg-slate-950 text-slate-200">
      <div className="pointer-events-none absolute inset-0 -z-10 bg-grid-faint [background-size:44px_44px]" />
      <SiteNav />

      <div className="mx-auto max-w-3xl px-5 pb-24 pt-32">
        <p className="text-sm font-medium text-brand-400">Documentation</p>
        <h1 className="mt-2 text-4xl font-semibold tracking-tight text-white">
          Using Student Claw
        </h1>
        <p className="mt-4 text-lg text-slate-400">
          A multi-mode AI agent that lives in your Telegram group and syncs to a web
          dashboard. Here&apos;s how it works.
        </p>

        <div className="mt-14 space-y-14">
          <Section id="start" title="Getting started">
            <ol className="list-decimal space-y-2 pl-5">
              <li>Add <code className="text-brand-300">@sutdclaw_bot</code> to your group chat.</li>
              <li>It registers the project and replies with a Project Key.</li>
              <li>Register on the web dashboard, submit the key, and run <code className="text-brand-300">/verify &lt;token&gt;</code> in the group.</li>
              <li>Open <code className="text-brand-300">/sc</code> for the full menu.</li>
            </ol>
          </Section>

          <Section id="commands" title="Commands">
            <div className="overflow-hidden rounded-2xl border border-white/10">
              <table className="w-full text-left text-sm">
                <tbody className="divide-y divide-white/10">
                  {COMMANDS.map(([cmd, desc]) => (
                    <tr key={cmd} className="bg-white/[0.02]">
                      <td className="whitespace-nowrap px-4 py-3 font-mono text-brand-300">{cmd}</td>
                      <td className="px-4 py-3 text-slate-400">{desc}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="text-sm">
              Everything else lives inside the <code className="text-brand-300">/sc</code> inline menu — no commands to memorise.
            </p>
          </Section>

          <Section id="agnes" title="How Agnes processes your data">
            <p>
              Every message, image and document shared in the group is captured and turned
              into searchable knowledge:
            </p>
            <ul className="list-disc space-y-2 pl-5">
              <li><span className="text-slate-200">Multi-modal ingestion.</span> Text is stored as-is; images and scanned PDFs are read by <span className="text-brand-300">Qwen-2.5-VL</span>; slide decks and text PDFs are parsed directly.</li>
              <li><span className="text-slate-200">Vector memory.</span> Extracted text is embedded locally and stored in a per-project vector space, so Agnes can recall the exact passage you ask about.</li>
              <li><span className="text-slate-200">Grounded answers.</span> When you <code className="text-brand-300">/ask</code>, Agnes retrieves the most relevant snippets and answers from them — never inventing facts.</li>
              <li><span className="text-slate-200">Resilience.</span> If the primary model is unavailable, a Gemini fallback keeps answers flowing.</li>
            </ul>
          </Section>

          <Section id="faq" title="FAQ">
            <div className="space-y-3">
              {FAQ.map(([q, a]) => (
                <details
                  key={q}
                  className="group rounded-2xl border border-white/10 bg-white/[0.02] p-5 open:border-brand-500/30"
                >
                  <summary className="cursor-pointer list-none font-medium text-slate-100 marker:hidden">
                    <span className="flex items-center justify-between">
                      {q}
                      <span className="text-brand-400 transition-transform group-open:rotate-45">+</span>
                    </span>
                  </summary>
                  <p className="mt-3 text-sm text-slate-400">{a}</p>
                </details>
              ))}
            </div>
          </Section>
        </div>

        <div className="mt-16 rounded-2xl border border-white/10 bg-gradient-to-br from-brand-500/10 to-transparent p-8 text-center">
          <h3 className="text-xl font-semibold text-white">Ready to try it?</h3>
          <Link
            href="/register"
            data-magnetic
            className="mt-4 inline-flex rounded-xl bg-brand-500 px-6 py-3 font-semibold text-white shadow-glow transition-transform hover:scale-[1.03]"
          >
            Get started free
          </Link>
        </div>
      </div>
    </main>
  );
}
