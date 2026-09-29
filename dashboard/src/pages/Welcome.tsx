import { useNavigate } from 'react-router-dom';
import Logo from '../components/Logo';
import { ArrowRight } from 'lucide-react';
import Ferrofluid from '../components/ui/Ferrofluid';

export default function Welcome() {
  const navigate = useNavigate();

  return (
    <div className="relative min-h-screen bg-slate-950 overflow-hidden flex flex-col items-center justify-center text-slate-200 select-none font-sans">
      <div className="absolute inset-0 -z-10">
        <Ferrofluid colors={["#ef4444", "#0f172a", "#1e293b"]} speed={0.4} scale={1.2} glow={3} mouseInteraction={true} />
      </div>

      <div className="relative z-10 flex flex-col items-center animate-in fade-in zoom-in-95 duration-1000 ease-out fill-mode-forwards">
        <div className="w-24 h-24 rounded-3xl bg-slate-900/80 backdrop-blur-md border border-slate-800 shadow-2xl flex items-center justify-center mb-8 p-3 hover:border-red-500/50 hover:shadow-[0_0_30px_rgba(220,38,38,0.2)] transition-all duration-500 group animate-in fade-in slide-in-from-bottom-4 duration-700 delay-100 fill-mode-both">
          <Logo page="probes" size={72} />
        </div>
        
        <h1 className="text-5xl md:text-7xl font-extrabold tracking-tight bg-clip-text text-transparent bg-gradient-to-b from-white to-slate-400 font-display text-center animate-in fade-in slide-in-from-bottom-4 duration-700 delay-300 fill-mode-both">
          ScrapeBuster
        </h1>
        
        <p className="font-mono text-sm md:text-base text-red-400/80 tracking-widest uppercase mt-4 mb-10 text-center max-w-lg animate-in fade-in slide-in-from-bottom-4 duration-700 delay-500 fill-mode-both">
          Active Offensive Provenance for AI Data Theft.
        </p>
        
        <button 
          onClick={() => navigate('/dashboard')}
          className="group relative px-8 py-4 bg-slate-900/50 backdrop-blur-md border border-slate-700 rounded-lg text-slate-100 font-mono tracking-wide transition-all duration-300 hover:border-red-500 hover:shadow-[0_0_30px_rgba(220,38,38,0.3)] hover:-translate-y-1 animate-in fade-in slide-in-from-bottom-4 duration-700 delay-700 fill-mode-both"
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
