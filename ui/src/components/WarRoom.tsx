import { useState, useEffect, useRef } from 'react';
import { 
  Shield, 
  Terminal as TerminalIcon, 
  Globe, 
  Zap, 
  Activity,
  User
} from 'lucide-react';

/**
 * K1 War Room Dashboard (Stage 25).
 * WebSocket-driven real-time instrumentation for the K1 Swarm.
 */
export const WarRoom = () => {
  const [logs, setLogs] = useState<string[]>([]);
  const activeFleet = [
    { id: 'aws-1', provider: 'AWS', ip: '3.x.x.x', status: 'active' },
    { id: 'gcp-1', provider: 'GCP', ip: '34.x.x.x', status: 'active' },
    { id: 'oci-1', provider: 'OCI', ip: '129.x.x.x', status: 'active' }
  ];
  const scans = [
    { id: 'scan-1', target: 'global-bank.com', progress: 65, status: 'exploiting' },
    { id: 'scan-2', target: 'social-connect.net', progress: 30, status: 'scanning' },
    { id: 'scan-3', target: 'crypto-ex.io', progress: 95, status: 'reporting' }
  ];
  const logEndRef = useRef<HTMLDivElement>(null);

  const ralphQuotes = [
    "Scanning targets... try not to fall asleep at the console, Commander.",
    "I'm helping! My brain is a vulnerability scanner!",
    "That WAF looks like a cookie. I want to eat it.",
    "I'm a security researcher! Look at my keyboard!",
    "Sovereignty is better than red crayons."
  ];

  const [currentQuote, setCurrentQuote] = useState(ralphQuotes[0]);

  useEffect(() => {
    // Simulated WebSocket Log Stream
    const interval = setInterval(() => {
      const timestamp = new Date().toLocaleTimeString();
      const newLog = `[${timestamp}] ${activeFleet[Math.floor(Math.random() * 3)].provider} -> Executing Nuclei scan on target...`;
      setLogs(prev => [...prev.slice(-50), newLog]);
      
      // Random Ralph Quote
      if (Math.random() > 0.8) {
        setCurrentQuote(ralphQuotes[Math.floor(Math.random() * ralphQuotes.length)]);
      }
    }, 2000);

    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  return (
    <div className="flex flex-col h-screen bg-black text-gold-main font-mono overflow-hidden">
      {/* Header */}
      <div className="flex justify-between items-center p-4 border-b border-gold-dark/30 bg-black/80 backdrop-blur-md z-50">
        <div className="flex items-center gap-4">
          <div className="w-10 h-10 rounded-full bg-gradient-to-br from-gold-light via-gold-main to-gold-dark flex items-center justify-center border-2 border-black shadow-[0_0_15px_rgba(255,215,0,0.5)]">
            <Shield className="text-black w-6 h-6" />
          </div>
          <h1 className="text-2xl font-black italic tracking-tighter">K1 WAR ROOM</h1>
        </div>
        
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-2 px-3 py-1 bg-gold-main/5 border border-gold-dark/20 rounded-full">
            <Activity className="w-4 h-4 text-green-500 animate-pulse" />
            <span className="text-[10px] uppercase">Sovereign Link: ONLINE</span>
          </div>
          <div className="text-right">
            <div className="text-xs text-gray-500 uppercase">War Chest</div>
            <div className="text-lg font-bold text-gold-main">$124,500.00</div>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left: Swarm Map & Targets */}
        <div className="w-1/3 flex flex-col border-r border-gold-dark/20 p-4 gap-6">
          <section>
            <div className="flex items-center gap-2 mb-4 text-sm font-bold border-b border-gold-dark/10 pb-2">
              <Globe className="w-4 h-4" /> GLOBAL SWARM MAP
            </div>
            <div className="grid grid-cols-1 gap-2">
              {activeFleet.map(node => (
                <div key={node.id} className="flex justify-between items-center p-3 bg-white/5 rounded border border-gold-dark/10 hover:border-gold-main/40 transition-colors">
                  <div className="flex items-center gap-3">
                    <div className="w-2 h-2 rounded-full bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.8)]" />
                    <span className="text-xs font-bold">{node.provider}</span>
                  </div>
                  <span className="text-[10px] text-gray-500 font-mono">{node.ip}</span>
                </div>
              ))}
            </div>
          </section>

          <section className="flex-1">
            <div className="flex items-center gap-2 mb-4 text-sm font-bold border-b border-gold-dark/10 pb-2">
              <Zap className="w-4 h-4" /> CONCURRENT SCAN SLOTS
            </div>
            <div className="space-y-4">
              {scans.map(scan => (
                <div key={scan.id} className="space-y-2">
                  <div className="flex justify-between text-[10px] uppercase">
                    <span>{scan.target}</span>
                    <span className="text-gold-light">{scan.status} ({scan.progress}%)</span>
                  </div>
                  <div className="w-full bg-gray-900 rounded-full h-1.5 overflow-hidden border border-gold-dark/10">
                    <div 
                      className="bg-gold-main h-full rounded-full shadow-[0_0_10px_rgba(255,215,0,0.3)] transition-all duration-1000"
                      style={{ width: `${scan.progress}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </section>

          {/* Ralph Persona */}
          <section className="p-4 bg-blue-900/10 border border-blue-900/30 rounded-xl relative overflow-hidden group">
            <div className="absolute top-0 right-0 p-2 opacity-20 group-hover:opacity-100 transition-opacity">
              <User className="w-8 h-8 text-blue-400" />
            </div>
            <h3 className="text-[10px] font-bold text-blue-400 mb-2 uppercase tracking-widest">Ralph Intervention</h3>
            <p className="text-xs italic text-blue-200">"{currentQuote}"</p>
          </section>
        </div>

        {/* Right: Matrix Console */}
        <div className="flex-1 flex flex-col bg-black/90 p-4">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2 text-xs font-bold text-monokai-green">
              <TerminalIcon className="w-4 h-4" /> LIVE INTELLIGENCE STREAM
            </div>
            <div className="text-[10px] text-gray-600">ENCRYPTION: AES-256-GCM</div>
          </div>
          <div className="flex-1 overflow-y-auto font-mono text-[11px] space-y-1 pr-4 custom-scrollbar">
            {logs.map((log, i) => (
              <div key={i} className="text-monokai-green/80 hover:text-monokai-green transition-colors">
                <span className="opacity-40 mr-2">{">>>"}</span> {log}
              </div>
            ))}
            <div ref={logEndRef} />
          </div>
        </div>
      </div>

      {/* Side Panel Game: Hacker Tic-Tac-Toe (Conceptual) */}
      <div className="absolute bottom-4 left-4 w-48 p-3 bg-gray-900/80 border border-gold-dark/20 rounded-lg hidden lg:block">
        <h4 className="text-[9px] font-bold mb-2 uppercase">Ghost Game: Shell vs. Firewall</h4>
        <div className="grid grid-cols-3 gap-1 h-24">
          {[...Array(9)].map((_, i) => (
            <div key={i} className="border border-gold-dark/10 flex items-center justify-center hover:bg-gold-main/10 cursor-pointer text-xs">
              {i % 4 === 0 ? 'X' : i % 3 === 0 ? 'O' : ''}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
