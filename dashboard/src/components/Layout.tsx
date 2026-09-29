import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import { usePoll } from '../api/poll';
import { getHealth, getDemoStatus } from '../api/client';
import { 
  Activity, 
  Search, 
  Settings, 
  RefreshCw, 
  Command, 
  Bell, 
  Download, 
  FileText, 
  CheckCircle, 
  X, 
  Layers,
  Database,
  Cpu,
  Sun,
  Moon
} from 'lucide-react';
import { useState, useEffect } from 'react';
import Logo from './Logo';
import AboutModal from './AboutModal';

export default function Layout() {
  const { error: healthError, lastUpdated } = usePoll(getHealth, 1000);
  const { data: demo } = usePoll(getDemoStatus, 1000);
  const navigate = useNavigate();
  const location = useLocation();
  
  // Theme state: default to 'dark', sync with localStorage and <html>
  const [theme, setTheme] = useState<'dark' | 'light'>(() => {
    const saved = localStorage.getItem('sb_theme');
    if (saved === 'light' || saved === 'dark') return saved;
    return 'dark';
  });

  useEffect(() => {
    const root = document.documentElement;
    if (theme === 'light') {
      root.classList.add('light');
      root.classList.remove('dark');
    } else {
      root.classList.remove('light');
      root.classList.add('dark');
    }
    localStorage.setItem('sb_theme', theme);
  }, [theme]);

  const toggleTheme = () => {
    setTheme(prev => prev === 'dark' ? 'light' : 'dark');
  };

  const [cmdOpen, setCmdOpen] = useState(false);
  const [cmdQuery, setCmdQuery] = useState('');
  const [notifOpen, setNotifOpen] = useState(false);
  const [aboutOpen, setAboutOpen] = useState(false);
  const [exportOpen, setExportOpen] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [exportDone, setExportDone] = useState(false);
  const [unreadCount, setUnreadCount] = useState(3);

  const isError = !healthError;
  const isBreached = false;

  // Determine current active page for dynamic logo and navbar state
  const getCurrentPage = (): 'overview' | 'traffic' | 'canaries' | 'probes' | 'cases' => {
    const path = location.pathname;
    if (path.startsWith('/traffic')) return 'traffic';
    if (path.startsWith('/canaries')) return 'canaries';
    if (path.startsWith('/probes')) return 'probes';
    if (path.startsWith('/cases')) return 'cases';
    return 'overview';
  };

  const currentPage = getCurrentPage();

  const pageDetails = {
    overview: {
      badge: 'SENTINEL DEFENSE',
      sub: 'Real-time Threat Feed & Active SOC Telemetry',
      badgeColor: 'border-[#79b4b2]/50 text-[#79b4b2]',
    },
    traffic: {
      badge: 'SONAR RADAR',
      sub: 'L1/L2/L3 Traffic Analytics & Actor Fingerprints',
      badgeColor: 'border-[#79b4b2]/50 text-[#79b4b2]',
    },
    canaries: {
      badge: 'HONEY VAULT',
      sub: 'Synthetic Honeytokens & Knowledge Anchors',
      badgeColor: 'border-amber-500/50 text-amber-400',
    },
    probes: {
      badge: 'DOBERMAN PROBE',
      sub: 'Differential Interrogation & Leak Extraction',
      badgeColor: 'border-red-500/50 text-red-400',
    },
    cases: {
      badge: 'GPS PROVENANCE',
      sub: 'Cryptographic Attribution & Chain of Custody',
      badgeColor: 'border-[#aec7c6]/50 text-[#aec7c6]',
    },
  };

  const navDockItems = [
    {
      id: 'dashboard',
      path: '/',
      label: 'Overview & Threat Feed',
      page: 'overview' as const,
      sub: 'Sentinel Active Defense',
      iconPath: (
        <path d="M4 13h6a1 1 0 0 0 1-1V4a1 1 0 0 0-1-1H4a1 1 0 0 0-1 1v8a1 1 0 0 0 1 1zm-1 7a1 1 0 0 0 1 1h6a1 1 0 0 0 1-1v-4a1 1 0 0 0-1-1H4a1 1 0 0 0-1 1v4zm10 0a1 1 0 0 0 1 1h6a1 1 0 0 0 1-1v-7a1 1 0 0 0-1-1h-6a1 1 0 0 0-1 1v7zm1-10h6a1 1 0 0 0 1-1V4a1 1 0 0 0-1-1h-6a1 1 0 0 0-1 1v5a1 1 0 0 0 1 1z" />
      ),
    },
    {
      id: 'profile',
      path: '/traffic',
      label: 'Traffic Intelligence',
      page: 'traffic' as const,
      sub: 'Adversary Radar & Volume',
      iconPath: (
        <path d="M12 2a5 5 0 1 0 5 5 5 5 0 0 0-5-5zm0 8a3 3 0 1 1 3-3 3 3 0 0 1-3 3zm9 11v-1a7 7 0 0 0-7-7h-4a7 7 0 0 0-7 7v1h2v-1a5 5 0 0 1 5-5h4a5 5 0 0 1 5 5v1z" />
      ),
    },
    {
      id: 'messages',
      path: '/canaries',
      label: 'Canaries & Honeytokens',
      page: 'canaries' as const,
      sub: 'Decoy Knowledge Traps',
      iconPath: (
        <>
          <path d="M5 18v3.766l1.515-.909L11.277 18H16c1.103 0 2-.897 2-2V8c0-1.103-.897-2-2-2H4c-1.103 0-2 .897-2 2v8c0 1.103.897 2 2 2h1zM4 8h12v8h-5.277L7 18.234V16H4V8z" />
          <path d="M20 2H8c-1.103 0-2 .897-2 2h12c1.103 0 2 .897 2 2v8c1.103 0 2-.897 2-2V4c0-1.103-.897-2-2-2z" />
        </>
      ),
    },
    {
      id: 'help',
      path: '/probes',
      label: 'Doberman Interrogator',
      page: 'probes' as const,
      sub: 'Differential Model Probing',
      iconPath: (
        <>
          <path d="M11.953 2C6.465 2 2 6.486 2 12s4.486 10 10 10 10-4.486 10-10S17.493 2 11.953 2zM12 20c-4.411 0-8-3.589-8-8s3.567-8 7.953-8C16.391 4 20 7.589 20 12s-3.589 8-8 8z" />
          <path d="M11 7h2v7h-2zm0 8h2v2h-2z" />
        </>
      ),
    },
    {
      id: 'settings',
      path: '/cases',
      label: 'GPS Tracker & Provenance',
      page: 'cases' as const,
      sub: 'Chain-of-Custody Forensics',
      iconPath: (
        <>
          <path d="M12 16c2.206 0 4-1.794 4-4s-1.794-4-4-4-4 1.794-4 4 1.794 4 4 4zm0-6c1.084 0 2 .916 2 2s-.916 2-2 2-2-.916-2-2 .916-2 2-2z" />
          <path d="m2.845 16.136 1 1.73c.531.917 1.809 1.261 2.73.73l.529-.306A8.1 8.1 0 0 0 9 19.402V20c0 1.103.897 2 2 2h2c1.103 0 2-.897 2-2v-.598a8.132 8.132 0 0 0 1.896-1.111l.529.306c.923.53 2.198.188 2.731-.731l.999-1.729a2.001 2.001 0 0 0-.731-2.732l-.505-.292a7.718 7.718 0 0 0 0-2.224l.505-.292a2.002 2.002 0 0 0 .731-2.732l-.999-1.729c-.531-.92-1.808-1.265-2.731-.732l-.529.306A8.1 8.1 0 0 0 15 4.598V4c0-1.103-.897-2-2-2h-2c-1.103 0-2 .897-2 2v.598a8.132 8.132 0 0 0-1.896 1.111l-.529-.306c-.924-.531-2.2-.187-2.731.732l-.999 1.729a2.001 2.001 0 0 0 .731 2.732l.505.292a7.683 7.683 0 0 0 0 2.223l-.505.292a2.003 2.003 0 0 0-.731 2.733zm3.326-2.758A5.703 5.703 0 0 1 6 12c0-.462.058-.926.17-1.378a.999.999 0 0 0-.47-1.108l-1.123-.65.998-1.729 1.145.662a.997.997 0 0 0 1.188-.142 6.071 6.071 0 0 1 2.384-1.399A1 1 0 0 0 11 5.3V4h2v1.3a1 1 0 0 0 .708.956 6.083 6.083 0 0 1 2.384 1.399.999.999 0 0 0 1.188.142l1.144-.661 1 1.729-1.124.649a1 1 0 0 0-.47 1.108c.112.452.17.916.17 1.378 0 .461-.058.925-.171 1.378a1 1 0 0 0 .471 1.108l1.123.649-.998 1.729-1.145-.661a.996.996 0 0 0-1.188.142 6.071 6.071 0 0 1-2.384 1.399A1 1 0 0 0 13 18.7l.002 1.3H11v-1.3a1 1 0 0 0-.708-.956 6.083 6.083 0 0 1-2.384-1.399.992.992 0 0 0-1.188-.141l-1.144.662-1-1.729 1.124-.651a1 1 0 0 0 .471-1.108z" />
        </>
      ),
    },
  ];

  const notifications = [
    {
      id: 'notif-1',
      title: 'Provenance Signal Confirmed',
      desc: 'Target model output matched canary SB-CAN-0003 verbatim.',
      time: '2m ago',
      type: 'threat',
      link: '/cases/SB-001',
    },
    {
      id: 'notif-2',
      title: 'Decoy Honeytoken Tripped',
      desc: 'Session sb-soph3scrpr01 accessed hidden route /docs/api.',
      time: '14m ago',
      type: 'warning',
      link: '/canaries',
    },
    {
      id: 'notif-3',
      title: 'Automated Rate-Limit Imposed',
      desc: 'IP 192.168.1.44 throttled under L1 anti-scraper heuristic.',
      time: '28m ago',
      type: 'info',
      link: '/traffic',
    },
  ];

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setCmdOpen(prev => !prev);
      }
      if (e.key === 'Escape') {
        setCmdOpen(false);
        setNotifOpen(false);
        setExportOpen(false);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  const handleExport = () => {
    setExporting(true);
    setTimeout(() => {
      setExporting(false);
      setExportDone(true);
      setTimeout(() => {
        setExportDone(false);
        setExportOpen(false);
      }, 1500);
    }, 1200);
  };

  return (
    <div className="h-screen bg-slate-950 text-slate-300 flex flex-col font-sans overflow-hidden select-none transition-colors duration-250">
      {/* Top Banner for API Error */}
      {isError && (
        <div className="bg-red-900/40 text-red-400 px-4 py-1.5 text-center text-xs font-medium flex items-center justify-center gap-2 shrink-0 border-b border-red-900/50">
          <Activity size={14} />
          <span>API unreachable — showing cached telemetry from {lastUpdated?.toLocaleTimeString() ?? 'recent sync'}</span>
        </div>
      )}
      
      {/* Golden Run Banner */}
      {demo?.mode === 'golden' && (
        <div className="bg-amber-500/10 text-amber-500 px-4 py-1 text-center text-xs font-bold uppercase tracking-wider shrink-0 border-b border-amber-500/20">
          RECORDED RUN ACTIVE
        </div>
      )}

      {/* SaaS Header with DYNAMIC LOGO that transforms with the active page */}
      <header className="bg-slate-950 border-b border-slate-800 h-14 flex items-center justify-between px-5 shrink-0 z-20 transition-colors duration-250">
        {/* Left: Dynamic ScrapeBuster Logo (Click to open About & Terms modal) */}
        <div 
          onClick={() => setAboutOpen(true)} 
          className="flex items-center gap-3 w-80 cursor-pointer group"
          title="Click to view About ScrapeBuster & Terms of Service"
        >
          <div className="w-10 h-10 rounded-xl bg-slate-900 border border-slate-800 flex items-center justify-center shadow-lg p-1 group-hover:border-blue-400 group-hover:shadow-[0_0_15px_rgba(121,180,178,0.25)] transition-all duration-300">
            <Logo size={32} page={currentPage} />
          </div>
          <div className="flex flex-col">
            <div className="flex items-center gap-2">
              <h1 className="text-sm font-bold text-slate-100 tracking-tight font-display">
                ScrapeBuster
              </h1>
              <span className={`text-[9px] uppercase px-1.5 py-0.5 rounded bg-slate-900 font-mono font-bold border ${pageDetails[currentPage].badgeColor}`}>
                {pageDetails[currentPage].badge}
              </span>
            </div>
            <span className="text-[10px] text-slate-400 font-mono truncate max-w-[200px]" title={pageDetails[currentPage].sub}>
              {pageDetails[currentPage].sub}
            </span>
          </div>
        </div>
        
        {/* Center: Global Search Bar */}
        <div className="flex-1 flex justify-center max-w-xl">
          <div 
            onClick={() => setCmdOpen(true)}
            className="flex items-center gap-2 bg-slate-900/80 border border-slate-800 hover:border-slate-700 hover:bg-slate-850 transition-all px-3 py-1.5 rounded-lg w-full max-w-md cursor-pointer text-xs text-slate-400 shadow-inner group"
          >
            <Search size={14} className="text-slate-500 group-hover:text-slate-300 transition-colors" />
            <span className="flex-1 text-left font-mono">Search IPs, Rules, Provenance cases...</span>
            <div className="flex items-center gap-1 bg-slate-950 px-1.5 py-0.5 rounded text-[10px] font-mono border border-slate-800 text-slate-400">
              <Command size={10} />
              <span>K</span>
            </div>
          </div>
        </div>

        {/* Right: Global Status, Notifications, Theme Mode & Actions */}
        <div className="flex items-center justify-end gap-2.5 text-sm">
          {/* Protection Status Pill */}
          <div className="flex items-center gap-1.5 px-3 py-1 rounded-md text-xs font-mono font-medium border bg-slate-900/90 border-slate-800 shadow-sm">
            <div className={`w-2 h-2 rounded-full ${isBreached ? 'bg-red-500 animate-ping' : 'bg-blue-400 shadow-[0_0_8px_currentColor]'}`} />
            <span className={isBreached ? 'text-red-400 font-bold' : 'text-slate-200'}>
              {isBreached ? 'ACTIVE BREACH' : 'SYSTEM SECURE'}
            </span>
          </div>

          <div className="h-4 w-px bg-slate-800" />

          {/* Theme Mode Switcher Button (Light / Dark) */}
          <button
            onClick={toggleTheme}
            className="flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium text-slate-300 hover:text-slate-100 bg-slate-900 hover:bg-slate-800 rounded-md border border-slate-800 transition-all cursor-pointer shadow-sm"
            title={`Switch to ${theme === 'dark' ? 'Light' : 'Dark'} Mode`}
          >
            {theme === 'dark' ? (
              <>
                <Sun size={13} className="text-amber-400" />
                <span className="hidden sm:inline font-mono text-[11px]">Light Mode</span>
              </>
            ) : (
              <>
                <Moon size={13} className="text-blue-500" />
                <span className="hidden sm:inline font-mono text-[11px]">Dark Mode</span>
              </>
            )}
          </button>

          {/* Export Report Button */}
          <button 
            onClick={() => setExportOpen(true)}
            className="flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium text-slate-300 hover:text-white bg-slate-900 hover:bg-slate-800 rounded-md border border-slate-800 transition-colors cursor-pointer"
            title="Export SOC Report"
          >
            <Download size={13} className="text-slate-400" />
            <span className="hidden sm:inline">Export</span>
          </button>

          {/* Notifications Bell */}
          <div className="relative">
            <button 
              onClick={() => { setNotifOpen(!notifOpen); setUnreadCount(0); }}
              className="p-1.5 text-slate-400 hover:text-slate-200 hover:bg-slate-900 rounded-md transition-colors relative cursor-pointer"
              title="Notification Center"
            >
              <Bell size={16} />
              {unreadCount > 0 && (
                <span className="absolute top-0.5 right-0.5 w-2 h-2 bg-red-500 rounded-full animate-pulse" />
              )}
            </button>

            {/* Notification Dropdown Drawer */}
            {notifOpen && (
              <div className="absolute right-0 mt-2 w-80 bg-slate-900 border border-slate-800 rounded-xl shadow-2xl overflow-hidden z-50 animate-in fade-in slide-in-from-top-2 duration-150">
                <div className="p-3 border-b border-slate-800 flex items-center justify-between bg-slate-950/60">
                  <div className="flex items-center gap-2">
                    <Bell size={14} className="text-slate-400" />
                    <span className="text-xs font-bold text-slate-200 uppercase tracking-wider">SOC Alerts & Events</span>
                  </div>
                  <button onClick={() => setNotifOpen(false)} className="text-slate-500 hover:text-slate-300">
                    <X size={14} />
                  </button>
                </div>
                <div className="divide-y divide-slate-800/60 max-h-80 overflow-y-auto custom-scrollbar">
                  {notifications.map(n => (
                    <div 
                      key={n.id}
                      onClick={() => { navigate(n.link); setNotifOpen(false); }}
                      className="p-3 hover:bg-slate-800/60 cursor-pointer transition-colors"
                    >
                      <div className="flex items-center justify-between mb-1">
                        <span className={`text-[10px] font-bold uppercase tracking-wider px-1.5 py-0.2 rounded border ${
                          n.type === 'threat' ? 'bg-red-500/10 text-red-400 border-red-500/30' :
                          n.type === 'warning' ? 'bg-amber-500/10 text-amber-400 border-amber-500/30' :
                          'bg-blue-500/10 text-blue-400 border-blue-500/30'
                        }`}>
                          {n.title}
                        </span>
                        <span className="text-[10px] text-slate-500 font-mono">{n.time}</span>
                      </div>
                      <p className="text-xs text-slate-300 leading-snug">{n.desc}</p>
                    </div>
                  ))}
                </div>
                <div className="p-2 border-t border-slate-800 bg-slate-950/50 text-center">
                  <button onClick={() => { navigate('/cases'); setNotifOpen(false); }} className="text-[11px] text-blue-400 hover:text-blue-300 font-medium cursor-pointer">
                    View All Incident Logs →
                  </button>
                </div>
              </div>
            )}
          </div>
          
          <button className="p-1.5 text-slate-500 hover:text-slate-300 transition-colors cursor-pointer" title="Sync Status">
            <RefreshCw size={15} />
          </button>
          <button className="p-1.5 text-slate-500 hover:text-slate-300 transition-colors cursor-pointer" title="Settings">
            <Settings size={15} />
          </button>
        </div>
      </header>

      {/* Main App Layout */}
      <div className="flex flex-1 overflow-hidden relative">
        {/* Left Side Navigation: Perfectly matched color palette and proportioned dock */}
        <aside className="w-[72px] bg-slate-950 border-r border-slate-800 flex flex-col items-center py-4 shrink-0 z-10 justify-between select-none transition-colors duration-250">
          {/* Top Page Logo Emblem (Click to open About & Terms modal) */}
          <div 
            onClick={() => setAboutOpen(true)} 
            className="cursor-pointer group flex flex-col items-center gap-1"
            title="Click to view About ScrapeBuster & Terms of Service"
          >
            <div className="w-11 h-11 rounded-xl bg-slate-900 border border-slate-800 flex items-center justify-center shadow-md p-1 group-hover:border-blue-400 group-hover:shadow-[0_0_12px_rgba(121,180,178,0.25)] transition-all duration-300">
              <Logo size={32} page={currentPage} />
            </div>
            <span className="text-[8px] font-mono text-slate-500 uppercase tracking-widest font-semibold group-hover:text-blue-400 transition-colors">
              ABOUT
            </span>
          </div>

          {/* Uiverse.io Navbar Dock: perfectly matched to sidebar theme & palette */}
          <div className="flex flex-col justify-center items-center relative transition-all duration-[450ms] ease-in-out w-14 my-auto">
            <article className="border border-solid border-slate-800 w-full ease-in-out duration-500 left-0 rounded-2xl inline-block shadow-2xl bg-slate-900 overflow-visible">
              {navDockItems.map(item => {
                const isChecked = 
                  item.path === '/' 
                    ? location.pathname === '/' 
                    : location.pathname.startsWith(item.path);

                return (
                  <label
                    key={item.id}
                    htmlFor={item.id}
                    onClick={(e) => {
                      e.preventDefault();
                      navigate(item.path);
                    }}
                    className="has-[:checked]:shadow-lg relative w-full h-13 p-2.5 ease-in-out duration-300 border-solid border-transparent has-[:checked]:border-slate-700/60 has-[:checked]:bg-slate-800/80 group flex flex-row gap-3 items-center justify-center text-slate-400 has-[:checked]:text-blue-400 rounded-xl cursor-pointer transition-all"
                  >
                    <input
                      className="hidden peer/expand"
                      type="radio"
                      name="path"
                      id={item.id}
                      checked={isChecked}
                      readOnly
                    />

                    {/* Glowing active indicator bar on left */}
                    <span className="absolute left-1 w-1 h-5 rounded-full bg-blue-400 opacity-0 peer-checked/expand:opacity-100 transition-opacity duration-300 shadow-[0_0_8px_currentColor]" />

                    <svg
                      className="peer-hover/expand:scale-125 peer-hover/expand:text-blue-400 peer-hover/expand:fill-blue-400 peer-checked/expand:text-blue-400 peer-checked/expand:fill-blue-400 text-2xl peer-checked/expand:scale-125 ease-in-out duration-300 transition-all shrink-0"
                      xmlns="http://www.w3.org/2000/svg"
                      width="22"
                      height="22"
                      viewBox="0 0 24 24"
                      fill="currentColor"
                    >
                      {item.iconPath}
                    </svg>

                    {/* Floating Tooltip displaying Page Name & Unique Logo */}
                    <div className="pointer-events-none absolute left-full ml-3 px-3 py-1.5 rounded-xl bg-slate-900 border border-slate-700 text-slate-100 text-xs font-medium whitespace-nowrap opacity-0 group-hover:opacity-100 transition-all duration-200 translate-x-[-6px] group-hover:translate-x-0 shadow-2xl z-50 flex items-center gap-2.5">
                      <div className="w-6 h-6 rounded-lg bg-slate-950 border border-slate-700 flex items-center justify-center p-0.5">
                        <Logo page={item.page} size={18} />
                      </div>
                      <div className="flex flex-col text-left">
                        <span className="font-semibold text-xs leading-none text-slate-100">{item.label}</span>
                        <span className="text-[10px] text-blue-400 font-mono leading-tight">{item.sub}</span>
                      </div>
                    </div>
                  </label>
                );
              })}
            </article>
          </div>

          {/* Bottom Dock Actions: Theme Switcher & Search */}
          <div className="flex flex-col items-center gap-2">
            <button 
              onClick={toggleTheme}
              className="w-10 h-10 rounded-xl bg-slate-900 border border-slate-800 hover:border-slate-700 flex items-center justify-center text-slate-400 hover:text-slate-100 transition-all cursor-pointer shadow-sm group"
              title={`Switch to ${theme === 'dark' ? 'Light' : 'Dark'} Mode`}
            >
              {theme === 'dark' ? (
                <Sun size={16} className="text-amber-400 group-hover:rotate-45 transition-transform duration-300" />
              ) : (
                <Moon size={16} className="text-blue-500 group-hover:-rotate-12 transition-transform duration-300" />
              )}
            </button>
            <button 
              onClick={() => setCmdOpen(true)}
              className="w-10 h-10 rounded-xl bg-slate-900 border border-slate-800 hover:border-slate-700 flex items-center justify-center text-slate-400 hover:text-slate-200 transition-colors cursor-pointer shadow-sm"
              title="Search Command Palette (Cmd+K)"
            >
              <Search size={16} />
            </button>
            <div 
              className="w-2 h-2 rounded-full bg-blue-400 shadow-[0_0_8px_currentColor] animate-pulse" 
              title="SOC Telemetry Active"
            />
          </div>
        </aside>

        {/* Main Content Area */}
        <main className="flex-1 overflow-y-auto bg-slate-950 p-6 relative transition-colors duration-250">
          <Outlet />
        </main>
      </div>

      {/* Global Command Palette Modal (Cmd+K) */}
      {cmdOpen && (
        <div className="fixed inset-0 z-50 flex items-start justify-center pt-[12vh]">
          <div className="absolute inset-0 bg-slate-950/80 backdrop-blur-sm" onClick={() => setCmdOpen(false)} />
          <div className="relative bg-slate-900 border border-slate-800 rounded-xl shadow-2xl w-[580px] overflow-hidden flex flex-col">
            <div className="flex items-center border-b border-slate-800 px-4 py-3.5 bg-slate-950/50">
              <Search className="text-slate-500 mr-3" size={18} />
              <input 
                autoFocus
                type="text" 
                value={cmdQuery}
                onChange={e => setCmdQuery(e.target.value)}
                placeholder="Search IPs, jump to page, trigger probes..."
                className="flex-1 bg-transparent border-none outline-none text-slate-100 font-sans text-sm placeholder:text-slate-600"
              />
              <div className="bg-slate-800 text-slate-400 text-[10px] px-2 py-0.5 rounded font-mono border border-slate-700">ESC</div>
            </div>
            <div className="max-h-[380px] overflow-y-auto p-2">
              <div className="px-3 py-1.5 text-[10px] font-bold text-slate-500 uppercase tracking-wider">Navigation</div>
              <button onClick={() => { navigate('/'); setCmdOpen(false); }} className="w-full text-left flex items-center justify-between px-3 py-2 rounded-lg hover:bg-slate-800 text-slate-300 hover:text-slate-100 transition-colors text-xs">
                <span className="flex items-center gap-2.5"><Activity size={15} /> Overview & SOC Threat Feed</span>
                <span className="text-[10px] font-mono text-slate-500">Page 1</span>
              </button>
              <button onClick={() => { navigate('/traffic'); setCmdOpen(false); }} className="w-full text-left flex items-center justify-between px-3 py-2 rounded-lg hover:bg-slate-800 text-slate-300 hover:text-slate-100 transition-colors text-xs">
                <span className="flex items-center gap-2.5"><Activity size={15} /> Traffic Intelligence & Attack Surface</span>
                <span className="text-[10px] font-mono text-slate-500">Page 2</span>
              </button>
              <button onClick={() => { navigate('/canaries'); setCmdOpen(false); }} className="w-full text-left flex items-center justify-between px-3 py-2 rounded-lg hover:bg-slate-800 text-slate-300 hover:text-slate-100 transition-colors text-xs">
                <span className="flex items-center gap-2.5"><Layers size={15} /> Canaries & Honeytokens</span>
                <span className="text-[10px] font-mono text-slate-500">Page 3</span>
              </button>
              <button onClick={() => { navigate('/probes'); setCmdOpen(false); }} className="w-full text-left flex items-center justify-between px-3 py-2 rounded-lg hover:bg-slate-800 text-slate-300 hover:text-slate-100 transition-colors text-xs">
                <span className="flex items-center gap-2.5"><Cpu size={15} /> Doberman Probes Interrogation</span>
                <span className="text-[10px] font-mono text-slate-500">Page 4</span>
              </button>
              <button onClick={() => { navigate('/cases'); setCmdOpen(false); }} className="w-full text-left flex items-center justify-between px-3 py-2 rounded-lg hover:bg-slate-800 text-slate-300 hover:text-slate-100 transition-colors text-xs">
                <span className="flex items-center gap-2.5"><Database size={15} /> GPS Tracker & Provenance Pipeline</span>
                <span className="text-[10px] font-mono text-slate-500">Page 5</span>
              </button>

              <div className="px-3 py-1.5 mt-2 text-[10px] font-bold text-slate-500 uppercase tracking-wider">Quick Actions</div>
              <button onClick={() => { navigate('/probes'); setCmdOpen(false); }} className="w-full text-left flex items-center gap-2.5 px-3 py-2 rounded-lg hover:bg-slate-800 text-slate-300 hover:text-slate-100 transition-colors text-xs">
                <Cpu size={15} className="text-blue-400" /> <span>Run Doberman Probe Interrogation</span>
              </button>
              <button onClick={() => { setExportOpen(true); setCmdOpen(false); }} className="w-full text-left flex items-center gap-2.5 px-3 py-2 rounded-lg hover:bg-slate-800 text-slate-300 hover:text-slate-100 transition-colors text-xs">
                <Download size={15} className="text-emerald-400" /> <span>Generate Cryptographic Evidence Archive</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Export / Reporting Module Modal */}
      {exportOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-slate-950/80 backdrop-blur-sm" onClick={() => setExportOpen(false)} />
          <div className="relative bg-slate-900 border border-slate-800 rounded-xl shadow-2xl w-[480px] p-6 space-y-5">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2">
                <FileText className="text-blue-400" size={18} />
                <h3 className="text-sm font-bold text-slate-100 uppercase tracking-wider">Export Forensic SOC Report</h3>
              </div>
              <button onClick={() => setExportOpen(false)} className="text-slate-500 hover:text-slate-300">
                <X size={16} />
              </button>
            </div>

            <div className="space-y-3 text-xs">
              <label className="block text-slate-400 font-medium">Export Package Format</label>
              <div className="grid grid-cols-2 gap-2">
                <div className="p-3 rounded-lg border border-blue-500/40 bg-blue-500/10 cursor-pointer">
                  <div className="font-bold text-slate-200">PDF + Cryptographic Seal</div>
                  <div className="text-[10px] text-slate-400 mt-1">Court-admissible provenance report with SHA-256 evidence chain.</div>
                </div>
                <div className="p-3 rounded-lg border border-slate-800 bg-slate-950/50 hover:border-slate-700 cursor-pointer">
                  <div className="font-bold text-slate-200">STIX 2.1 Threat Intel</div>
                  <div className="text-[10px] text-slate-400 mt-1">Structured IOCs, adversary actor profiles, and honeytoken signals.</div>
                </div>
              </div>
            </div>

            <div className="space-y-2 text-xs">
              <label className="block text-slate-400 font-medium">Incident Scope</label>
              <div className="p-2.5 rounded bg-slate-950 border border-slate-800 font-mono text-slate-300">
                Incident SB-001 (Canary SB-CAN-0003, Model qwen2.5:3b)
              </div>
            </div>

            <div className="flex items-center justify-end gap-3 pt-2">
              <button 
                onClick={() => setExportOpen(false)}
                className="px-3 py-1.5 rounded text-xs text-slate-400 hover:text-slate-200 transition-colors"
              >
                Cancel
              </button>
              <button 
                onClick={handleExport}
                disabled={exporting || exportDone}
                className="flex items-center gap-2 px-4 py-2 rounded text-xs font-semibold bg-blue-600 hover:bg-blue-500 text-white transition-all disabled:opacity-50"
              >
                {exporting && <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />}
                {exportDone && <CheckCircle size={14} className="text-emerald-300" />}
                {exportDone ? 'Report Generated' : exporting ? 'Compiling Manifest...' : 'Generate & Download'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* About ScrapeBuster & Terms of Service Modal (Triggered by Logo) */}
      <AboutModal open={aboutOpen} onOpenChange={setAboutOpen} />
    </div>
  );
}


