import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { Shield, Zap, Globe, Cpu } from 'lucide-react';

/**
 * K1 TopHUD Component (Stage 18).
 * Features the rotating Kaison AI Medallion and 'Sovereign Status' HUD.
 */
export default function TopHUD() {
  const [health, setHealth] = useState<'OK' | 'DOWN' | '...'>('...');
  const [ws, setWs] = useState<'ON' | 'OFF'>('OFF');
  const API = (import.meta.env.VITE_API_BASE || (localStorage.getItem('API_BASE') || 'http://localhost:8080'));

  useEffect(() => {
    let t: any;
    const check = async () => {
      try {
        await axios.get(API + '/healthz', { timeout: 2000 });
        setHealth('OK');
      } catch {
        setHealth('DOWN');
      }
      t = setTimeout(check, 5000);
    };
    check();
    return () => { if (t) clearTimeout(t); };
  }, [API]);

  useEffect(() => {
    try {
      const wsurl = API.replace('http', 'ws') + '/ws';
      const w = new WebSocket(wsurl);
      w.onopen = () => setWs('ON');
      w.onclose = () => setWs('OFF');
      return () => { try { w.close(); } catch (e) { } };
    } catch (e) { setWs('OFF'); }
  }, [API]);

  return (
    <div className="topbar">
      {/* Left HUD: Medallion & Identity */}
      <div className="left">
        <div className="logo-container">
          <div className="medallion">
            <Shield className="text-black w-6 h-6" />
          </div>
          <div className="flex flex-col">
            <span className="text-gold-main font-black text-lg tracking-tighter leading-none">KAISON AI</span>
            <span className="text-[10px] text-gray-500 font-mono uppercase tracking-widest">Sovereign Engine v1.0.0</span>
          </div>
        </div>
        
        <div className="h-8 w-[1px] bg-gray-800 mx-2" />
        
        <div className="flex items-center gap-2 px-3 py-1 bg-black border border-gold-dark/30 rounded-md">
          <Globe className={`w-3 h-3 ${health === 'OK' ? 'text-green-500' : 'text-orange-500'}`} />
          <span className="text-[10px] font-mono uppercase">API: {health}</span>
        </div>
        
        <div className="flex items-center gap-2 px-3 py-1 bg-black border border-gold-dark/30 rounded-md">
          <Zap className={`w-3 h-3 ${ws === 'ON' ? 'text-gold-main' : 'text-gray-600'}`} />
          <span className="text-[10px] font-mono uppercase">Sync: {ws}</span>
        </div>
      </div>

      {/* Center: Mission Active Pulse (Optional) */}
      <div className="hidden lg:flex items-center gap-4">
        <div className="px-4 py-1 border border-gold-main/20 rounded-full bg-gold-main/5">
          <span className="text-[9px] text-gold-main font-bold uppercase tracking-[0.3em] animate-pulse">
            Active Intelligence Stream • Intention Verified
          </span>
        </div>
      </div>

      {/* Right HUD: Operations Status */}
      <div className="right">
        <button className="btn-sovereign text-xs">
          COMMAND MODE
        </button>
        <div className="flex items-center gap-2 p-1 bg-gray-900 rounded-full border border-gray-800">
          <div className="w-8 h-8 rounded-full bg-gold-dark flex items-center justify-center border border-black">
            <Cpu className="w-4 h-4 text-black" />
          </div>
        </div>
      </div>
    </div>
  );
}
