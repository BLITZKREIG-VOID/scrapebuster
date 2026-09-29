import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Logo from '../components/Logo';
import { Key, Loader2 } from 'lucide-react';

export default function Login() {
  const navigate = useNavigate();
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    
    // Simulate network request
    setTimeout(() => {
      setIsLoading(false);
      navigate('/');
    }, 800);
  };

  return (
    <div className="min-h-screen bg-[#0d0f12] bg-[linear-gradient(to_right,#ffffff05_1px,transparent_1px),linear-gradient(to_bottom,#ffffff05_1px,transparent_1px)] bg-[size:32px_32px] flex items-center justify-center p-4 font-sans select-none relative overflow-hidden">
      
      {/* Ambient background glows */}
      <div className="absolute top-0 left-0 w-96 h-96 bg-red-500/20 blur-[120px] rounded-full pointer-events-none -translate-x-1/2 -translate-y-1/2" />
      <div className="absolute bottom-0 right-0 w-96 h-96 bg-cyan-500/10 blur-[120px] rounded-full pointer-events-none translate-x-1/2 translate-y-1/2" />

      <div className="w-full max-w-md bg-white/[0.03] backdrop-blur-xl border border-white/10 rounded-2xl shadow-2xl p-8 relative z-10 hover:border-white/20 transition-colors duration-500">
        <div className="relative z-10">
          <div className="flex flex-col items-center mb-8">
            <div className="w-16 h-16 rounded-2xl bg-black/40 border border-white/10 flex items-center justify-center mb-5 shadow-lg backdrop-blur-md">
              <Logo page="overview" size={40} />
            </div>
            <h1 className="text-2xl font-extrabold text-slate-100 tracking-tight font-display text-center drop-shadow-sm">
              Operator Authentication
            </h1>
            <p className="text-[10px] text-slate-400 font-mono mt-2 uppercase tracking-widest text-center opacity-80">
              SCRAPEBUSTER IDENTITY AWARE PROXY | v1.2
            </p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-5">
            <div className="space-y-1.5">
              <label className="text-[10px] uppercase tracking-widest text-slate-400 font-bold ml-1">
                OPERATOR ID / EMAIL
              </label>
              <input 
                type="text" 
                required
                disabled={isLoading}
                placeholder="opr-998-alpha"
                className="w-full bg-black/20 border border-white/10 rounded-lg px-4 py-3 text-sm font-mono text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-red-500 focus:ring-1 focus:ring-red-500 transition-all disabled:opacity-50"
              />
            </div>
            
            <div className="space-y-1.5">
              <label className="text-[10px] uppercase tracking-widest text-slate-400 font-bold ml-1">
                ACCESS TOKEN / PASSWORD
              </label>
              <input 
                type="password"
                required
                disabled={isLoading}
                placeholder="••••••••••••••••"
                className="w-full bg-black/20 border border-white/10 rounded-lg px-4 py-3 text-sm font-mono text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-red-500 focus:ring-1 focus:ring-red-500 transition-all disabled:opacity-50"
              />
            </div>

            <button 
              type="submit"
              disabled={isLoading}
              className="w-full mt-8 group relative px-6 py-4 bg-red-600 hover:bg-red-500 text-white rounded-lg font-bold text-sm tracking-widest uppercase overflow-hidden transition-all duration-300 shadow-[0_0_20px_rgba(225,29,72,0.3)] hover:shadow-[0_0_30px_rgba(225,29,72,0.5)] hover:scale-[1.02] disabled:opacity-70 disabled:scale-100 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            >
              {isLoading ? (
                <>
                  <Loader2 size={18} className="animate-spin" />
                  <span>Verifying...</span>
                </>
              ) : (
                <>
                  <Key size={16} className="text-red-100 group-hover:rotate-12 transition-transform" />
                  <span>Request Access</span>
                </>
              )}
            </button>
          </form>
          
          <div className="mt-8 pt-6 border-t border-white/10 text-center flex flex-col gap-1">
            <p className="text-[9px] font-mono text-slate-500 uppercase tracking-wider">
              UNAUTHORIZED ACCESS IS STRICTLY PROHIBITED AND MONITORED.
            </p>
            <p className="text-[9px] font-mono text-slate-600 uppercase tracking-wider">
              Scrapebuster Security Team
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
