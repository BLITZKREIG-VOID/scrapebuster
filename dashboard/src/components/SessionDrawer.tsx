import { useState, useEffect } from 'react';
import { getSession } from '../api/client';
import type { SessionDetail } from '../types/contracts';
import { X, ExternalLink } from 'lucide-react';
import { Link } from 'react-router-dom';

interface Props {
  sessionId: string | null;
  onClose: () => void;
  reasonMap: Record<string, string>;
}

export default function SessionDrawer({ sessionId, onClose, reasonMap }: Props) {
  const [response, setResponse] = useState<{ sessionId: string; detail: SessionDetail | null; error: string | null } | null>(null);

  useEffect(() => {
    if (!sessionId) return;
    let active = true;
    getSession(sessionId)
      .then(data => {
        if (active) setResponse({ sessionId, detail: data, error: null });
      })
      .catch((e: unknown) => {
        if (active) setResponse({ sessionId, detail: null, error: e instanceof Error ? e.message : 'Failed to load session details' });
      });

    return () => {
      active = false;
    };
  }, [sessionId]);

  if (!sessionId) return null;

  const currentResponse = response?.sessionId === sessionId ? response : null;
  const detail = currentResponse?.detail ?? null;
  const error = currentResponse?.error ?? '';
  const loading = !currentResponse;

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-slate-900/50 backdrop-blur-sm">
      <div className="w-[600px] h-full bg-slate-800 border-l border-slate-700 shadow-2xl flex flex-col transform transition-transform animate-in slide-in-from-right duration-300">
        <div className="flex items-center justify-between p-4 border-b border-slate-700 bg-slate-900/50">
          <h2 className="text-lg font-semibold text-slate-100 flex items-center gap-2">
            Session Profile
            <span className="text-xs font-mono bg-slate-700 px-2 py-1 rounded text-slate-300">{sessionId}</span>
          </h2>
          <button onClick={onClose} className="p-1.5 hover:bg-slate-700 rounded text-slate-400 hover:text-slate-100 transition-colors">
            <X size={20} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {loading && <div className="text-slate-400 flex items-center gap-2"><div className="w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full animate-spin"></div> Loading profile...</div>}
          {error && <div className="text-red-400 bg-red-500/10 p-4 rounded border border-red-500/20">{error}</div>}
          
          {detail && (
            <>
              {/* Meta */}
              <div className="grid grid-cols-2 gap-4">
                <div className="bg-slate-900/50 p-3 rounded border border-slate-700">
                  <div className="text-[10px] uppercase font-bold text-slate-500 mb-1">Decision</div>
                  <div className={`text-sm font-bold font-mono ${detail.decision === 'SANDBOX' ? 'text-purple-400' : 'text-emerald-400'}`}>
                    {detail.decision}
                  </div>
                </div>
                <div className="bg-slate-900/50 p-3 rounded border border-slate-700">
                  <div className="text-[10px] uppercase font-bold text-slate-500 mb-1">Risk Score</div>
                  <div className="text-sm font-medium font-mono text-slate-200">{detail.risk_score}</div>
                </div>
                <div className="bg-slate-900/50 p-3 rounded border border-slate-700">
                  <div className="text-[10px] uppercase font-bold text-slate-500 mb-1">Classification</div>
                  <div className="text-sm font-medium text-slate-200">{detail.classification.replace(/_/g, ' ')}</div>
                </div>
                <div className="bg-slate-900/50 p-3 rounded border border-slate-700">
                  <div className="text-[10px] uppercase font-bold text-slate-500 mb-1">State</div>
                  <div className="text-sm font-medium text-slate-200">{detail.state}</div>
                </div>
                <div className="bg-slate-900/50 p-3 rounded border border-slate-700">
                  <div className="text-[10px] uppercase font-bold text-slate-500 mb-1">Client Key / IP</div>
                  <div className="text-sm font-mono text-slate-300">{detail.client_key} <span className="text-slate-500 text-xs">({detail.ip})</span></div>
                </div>
                <div className="bg-slate-900/50 p-3 rounded border border-slate-700">
                  <div className="text-[10px] uppercase font-bold text-slate-500 mb-1">Requests</div>
                  <div className="text-sm font-mono text-slate-300">{detail.request_count}</div>
                </div>
                <div className="bg-slate-900/50 p-3 rounded border border-slate-700 col-span-2">
                  <div className="text-[10px] uppercase font-bold text-slate-500 mb-1">User Agent</div>
                  <div className="text-xs font-mono text-slate-400 break-all">{detail.user_agent}</div>
                </div>
              </div>

              {/* Reasons & Signals */}
              {detail.reasons && detail.reasons.length > 0 && (
                <div className="border border-slate-700 rounded overflow-hidden">
                  <div className="bg-slate-900/80 p-2 text-xs font-bold uppercase tracking-wider text-slate-400 border-b border-slate-700">
                    Evaluation Reasons
                  </div>
                  <div className="p-3 bg-slate-800">
                    <ul className="list-disc pl-5 text-sm text-slate-300 space-y-1">
                      {detail.reasons.map((r, i) => <li key={i}>{reasonMap[r] || r}</li>)}
                    </ul>
                  </div>
                </div>
              )}

              {/* Pages Visited */}
              {detail.pages && detail.pages.length > 0 && (
                <div className="border border-slate-700 rounded overflow-hidden">
                  <div className="bg-slate-900/80 p-2 text-xs font-bold uppercase tracking-wider text-slate-400 border-b border-slate-700">
                    Pages Visited
                  </div>
                  <div className="p-3 bg-slate-800">
                    <div className="flex flex-wrap gap-1.5">
                      {detail.pages.map((p, i) => (
                        <span key={i} className="px-2 py-0.5 bg-slate-900 text-slate-300 font-mono text-xs rounded border border-slate-700">
                          {p}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
              )}

              {/* Offenses & Canaries */}
              {(detail.traps_triggered.length > 0 || detail.canaries_exposed.length > 0) && (
                <div className="bg-purple-900/10 border border-purple-500/20 rounded p-4">
                  <h3 className="text-sm font-semibold text-purple-400 mb-3 uppercase tracking-wider">Offensive Deception</h3>
                  <div className="space-y-4">
                    {detail.traps_triggered.length > 0 && (
                      <div>
                        <div className="text-xs font-medium text-slate-400 mb-1">Offense Hooks Triggered</div>
                        <div className="flex flex-wrap gap-2">
                          {detail.traps_triggered.map(t => (
                            <span key={t} className="px-2 py-1 bg-slate-900 rounded text-xs font-mono text-purple-300 border border-purple-500/30">
                              {reasonMap[t] || t}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                    {detail.canaries_exposed.length > 0 && (
                      <div>
                        <div className="text-xs font-medium text-slate-400 mb-1">Canaries Exposed</div>
                        <div className="flex flex-wrap gap-2">
                          {detail.canaries_exposed.map(c => (
                            <Link key={c} to="/canaries" className="flex items-center gap-1 px-2 py-1 bg-slate-900 rounded text-xs font-mono text-blue-400 border border-blue-500/30 hover:bg-blue-900/30 transition-colors">
                              {c} <ExternalLink size={10} />
                            </Link>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
