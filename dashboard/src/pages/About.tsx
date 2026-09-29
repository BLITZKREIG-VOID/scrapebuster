import { Shield, Sparkles, Binary, AlertOctagon, Terminal } from 'lucide-react';
import Logo from '../components/Logo';

export default function About() {
  return (
    <div className="max-w-4xl mx-auto space-y-8 pb-12 select-none animate-in fade-in slide-in-from-bottom-4 duration-500 pt-8">
      <div className="flex items-center gap-4">
        <div className="w-16 h-16 rounded-2xl bg-slate-900 border border-slate-800 flex items-center justify-center p-1.5 shadow-lg shrink-0">
          <Logo size={48} page="overview" />
        </div>
        <div className="flex flex-col text-left">
          <div className="flex items-center gap-3 flex-wrap">
            <h1 className="text-5xl font-extrabold text-slate-100 tracking-tight font-display">
              ScrapeBuster — Offensive Data Provenance
            </h1>
          </div>
          <span className="text-sm text-slate-400 font-mono mt-1">
            Autonomous Anti-Scraper Honeypots & LLM Training Attribution
          </span>
        </div>
      </div>

      <div className="text-base text-slate-300 leading-relaxed text-left bg-slate-900/50 p-6 rounded-2xl border border-slate-800/80 shadow-md">
        ScrapeBuster shifts web data protection from passive defense to active offense. Instead of just trying to block scrapers, we deploy invisible data canaries into scraped payloads. When an AI model trains on or retrieves our trapped data, our automated &apos;Doberman&apos; interrogator mathematically proves the theft.
      </div>

      <div className="space-y-4">
        <div className="text-sm font-bold uppercase tracking-wider text-slate-400 font-mono flex items-center gap-2">
          <Terminal size={16} className="text-blue-400" />
          <span>Multi-Stage Architecture</span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="flex flex-col gap-3 p-5 rounded-2xl bg-slate-900/80 border border-slate-800 hover:border-slate-700 transition-colors shadow-md">
            <div className="p-2 rounded-xl bg-blue-500/10 text-blue-400 border border-blue-500/20 w-fit">
              <Shield size={20} />
            </div>
            <div>
              <div className="font-bold text-slate-200 font-mono text-sm mb-1">L1 / L2 Edge Proxy</div>
              <div className="text-slate-400 text-sm leading-relaxed">Behavioral proxy blocking standard botnets with fingerprinting, header analysis, and interaction heuristics.</div>
            </div>
          </div>

          <div className="flex flex-col gap-3 p-5 rounded-2xl bg-slate-900/80 border border-slate-800 hover:border-slate-700 transition-colors shadow-md">
            <div className="p-2 rounded-xl bg-amber-500/10 text-amber-400 border border-amber-500/20 w-fit">
              <Sparkles size={20} />
            </div>
            <div>
              <div className="font-bold text-slate-200 font-mono text-sm mb-1">L3 Dynamic Trap</div>
              <div className="text-slate-400 text-sm leading-relaxed">Dynamic honeypots serving poisoned RAG data and synthetic watermarked knowledge anchors.</div>
            </div>
          </div>

          <div className="flex flex-col gap-3 p-5 rounded-2xl bg-slate-900/80 border border-slate-800 hover:border-slate-700 transition-colors shadow-md">
            <div className="p-2 rounded-xl bg-red-500/10 text-red-400 border border-red-500/20 w-fit">
              <Binary size={20} />
            </div>
            <div>
              <div className="font-bold text-slate-200 font-mono text-sm mb-1">Doberman Interrogator</div>
              <div className="text-slate-400 text-sm leading-relaxed">Deterministic LLM provenance verification using differential probe interrogation and court-admissible SHA-256 evidence seals.</div>
            </div>
          </div>
        </div>
      </div>

      <div className="space-y-3 pt-6 border-t border-slate-800/80">
        <div className="flex items-center gap-2 text-sm font-bold uppercase tracking-wider text-amber-400 font-mono">
          <AlertOctagon size={16} />
          <span>Terms of Use & Legal Notice</span>
        </div>

        <div className="p-5 rounded-2xl bg-slate-950 border border-slate-800/90 text-sm font-mono text-slate-400 leading-relaxed shadow-inner">
          <p>
            <strong className="text-slate-300">TERMS OF USE: </strong>
            ScrapeBuster is an active defense tool. By deploying these canaries, you verify that you are the legal owner of the origin data. Unauthorized deployment on third-party networks or use for malicious poisoning of open-source datasets is strictly prohibited. Use responsibly.
          </p>
        </div>
      </div>

    </div>
  );
}
