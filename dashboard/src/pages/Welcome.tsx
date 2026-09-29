import { useNavigate } from 'react-router-dom';
import Logo from '../components/Logo';
import { ArrowRight } from 'lucide-react';
import Ferrofluid from '../components/ui/Ferrofluid';

export default function Welcome() {
  const navigate = useNavigate();

  return (
    <div className="relative min-h-screen flex flex-col items-center justify-center overflow-hidden">
      {/* 1. Ferrofluid Base Layer (z-0) */}
      <div className="absolute inset-0 z-0">
        <Ferrofluid colors={["#ef4444", "#0f172a", "#1e293b"]} speed={0.4} scale={1.2} glow={3} mouseInteraction={true} opacity={0.8} />
      </div>



      {/* 3. Corner Text (z-20) */}
      <div className="absolute bottom-6 left-6 text-xs font-mono text-slate-500 z-20 pointer-events-none">SYS.BOOT_SEQ // OK<br/>L3.TRAP_STATUS // STANDBY</div>
      <div className="absolute bottom-6 right-6 text-xs font-mono text-slate-500 text-right z-20 pointer-events-none">SECURE ENCLAVE ACTIVE<br/>v0.9.4-hackathon</div>

      {/* 4. Main Content (z-30) */}
      <div className="relative z-30 flex flex-col items-center animate-in fade-in zoom-in-95 duration-1000 ease-out fill-mode-forwards">
        <div className="w-24 h-24 rounded-3xl bg-slate-900/80 backdrop-blur-md border border-slate-800 shadow-2xl flex items-center justify-center mb-8 p-3 hover:border-red-500/50 hover:shadow-[0_0_30px_rgba(220,38,38,0.2)] transition-all duration-500 group animate-in fade-in slide-in-from-bottom-4 duration-700 delay-100 fill-mode-both">
          <Logo page="probes" size={72} />
        </div>
        
        <h1 className="text-6xl md:text-8xl font-sans font-black tracking-tighter text-slate-100 drop-shadow-md animate-in fade-in slide-in-from-bottom-4 duration-700 delay-300 fill-mode-both">
          ScrapeBuster
        </h1>
        
        <div className="mt-6 px-4 py-1.5 rounded-full bg-red-950/30 border border-red-900/50 text-red-400 font-mono text-sm tracking-widest uppercase flex items-center gap-2 animate-in fade-in slide-in-from-bottom-4 duration-700 delay-500 fill-mode-both mb-10">
          <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse"></span>
          Active Offensive Provenance for AI Data Theft.
        </div>
        
        <button 
          onClick={() => navigate('/dashboard')}
          className="group relative px-8 py-4 bg-slate-900/50 backdrop-blur-md border border-slate-700 rounded-lg text-slate-100 font-mono tracking-wide hover:border-red-500 hover:shadow-[0_0_30px_rgba(220,38,38,0.3)] transition-all duration-300 hover:-translate-y-1 animate-in fade-in slide-in-from-bottom-4 duration-700 delay-700 fill-mode-both"
        >
          <span className="relative z-10 flex items-center justify-center gap-3">
            <span className="w-2 h-2 rounded-full bg-red-500 shadow-[0_0_10px_rgba(220,38,38,0.8)] animate-pulse" />
            Enter Command Center
            <ArrowRight size={16} className="transition-transform duration-300 group-hover:translate-x-1" />
          </span>
        </button>
      </div>
    </div>
  );
}
