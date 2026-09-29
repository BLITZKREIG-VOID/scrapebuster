import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from './ui/dialog';
import { Shield, Sparkles, Binary, AlertOctagon, Terminal } from 'lucide-react';
import Logo from './Logo';

interface AboutModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export default function AboutModal({ open, onOpenChange }: AboutModalProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl bg-slate-900 border-slate-800 text-slate-100 shadow-2xl p-6 sm:p-7">
        <DialogHeader className="space-y-3">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-xl bg-slate-950 border border-slate-800 flex items-center justify-center p-1 shadow-md shrink-0">
              <Logo size={36} page="overview" />
            </div>
            <div className="flex flex-col text-left">
              <div className="flex items-center gap-2 flex-wrap">
                <DialogTitle className="text-lg font-bold text-slate-100 tracking-tight font-display">
                  ScrapeBuster — Offensive Data Provenance
                </DialogTitle>
                <span className="font-mono text-[10px] px-2 py-0.5 rounded bg-blue-500/10 text-blue-400 border border-blue-500/30 uppercase tracking-widest font-semibold">
                  [POC Build - Hackathon Edition]
                </span>
              </div>
              <span className="text-xs text-slate-400 font-mono mt-0.5">
                Autonomous Anti-Scraper Honeypots & LLM Training Attribution
              </span>
            </div>
          </div>

          <DialogDescription className="text-xs text-slate-300 leading-relaxed text-left pt-2 border-t border-slate-800/80">
            ScrapeBuster shifts web data protection from passive defense to active offense. Instead of just trying to block scrapers, we deploy invisible data canaries into scraped payloads. When an AI model trains on or retrieves our trapped data, our automated &apos;Doberman&apos; interrogator mathematically proves the theft.
          </DialogDescription>
        </DialogHeader>

        {/* Architecture Pipeline List */}
        <div className="space-y-2.5 pt-1">
          <div className="text-[11px] font-bold uppercase tracking-wider text-slate-400 font-mono flex items-center gap-1.5">
            <Terminal size={13} className="text-blue-400" />
            <span>Multi-Stage Architecture</span>
          </div>

          <div className="grid grid-cols-1 gap-2 text-xs">
            <div className="flex items-start gap-3 p-3 rounded-xl bg-slate-950/70 border border-slate-800 hover:border-slate-700 transition-colors">
              <div className="p-1.5 rounded-lg bg-blue-500/10 text-blue-400 border border-blue-500/20 shrink-0 mt-0.5">
                <Shield size={14} />
              </div>
              <div>
                <span className="font-semibold text-slate-200 font-mono">L1 / L2 Edge: </span>
                <span className="text-slate-400">Behavioral proxy blocking standard botnets with fingerprinting, header analysis, and interaction heuristics.</span>
              </div>
            </div>

            <div className="flex items-start gap-3 p-3 rounded-xl bg-slate-950/70 border border-slate-800 hover:border-slate-700 transition-colors">
              <div className="p-1.5 rounded-lg bg-amber-500/10 text-amber-400 border border-amber-500/20 shrink-0 mt-0.5">
                <Sparkles size={14} />
              </div>
              <div>
                <span className="font-semibold text-slate-200 font-mono">L3 Trap: </span>
                <span className="text-slate-400">Dynamic honeypots serving poisoned RAG data and synthetic watermarked knowledge anchors.</span>
              </div>
            </div>

            <div className="flex items-start gap-3 p-3 rounded-xl bg-slate-950/70 border border-slate-800 hover:border-slate-700 transition-colors">
              <div className="p-1.5 rounded-lg bg-red-500/10 text-red-400 border border-red-500/20 shrink-0 mt-0.5">
                <Binary size={14} />
              </div>
              <div>
                <span className="font-semibold text-slate-200 font-mono">The Catch: </span>
                <span className="text-slate-400">Deterministic LLM provenance verification using differential probe interrogation and court-admissible SHA-256 evidence seals.</span>
              </div>
            </div>
          </div>
        </div>

        {/* Terms & Conditions Section */}
        <div className="space-y-2 pt-2 border-t border-slate-800/80">
          <div className="flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wider text-amber-400 font-mono">
            <AlertOctagon size={13} />
            <span>Terms of Use & Legal Notice</span>
          </div>

          <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800/90 text-[11px] font-mono text-slate-400 leading-relaxed max-h-28 overflow-y-auto custom-scrollbar select-text">
            <p>
              <strong className="text-slate-300">TERMS OF USE: </strong>
              ScrapeBuster is an active defense tool. By deploying these canaries, you verify that you are the legal owner of the origin data. Unauthorized deployment on third-party networks or use for malicious poisoning of open-source datasets is strictly prohibited. Use responsibly.
            </p>
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between pt-2 border-t border-slate-800/80 text-[11px] font-mono text-slate-500">
          <span className="flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
            <span>SOC Engine v1.2</span>
          </span>
          <button
            onClick={() => onOpenChange(false)}
            className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 font-medium transition-colors cursor-pointer text-xs"
          >
            Close
          </button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
