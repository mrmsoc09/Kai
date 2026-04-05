import React, { useState, useEffect } from 'react';
import { 
  Shield, 
  Activity, 
  Key, 
  Clock, 
  Zap, 
  AlertTriangle,
  RefreshCw
} from 'lucide-react';

// Simplified UI Components (assuming Tailwind CSS)
const Gauge = ({ label, used, limit, paused }) => {
  const percentage = Math.min((used / limit) * 100, 100);
  const color = paused ? 'bg-red-500' : percentage > 80 ? 'bg-orange-500' : 'bg-green-500';
  
  return (
    <div className="p-4 border border-gray-800 rounded-lg bg-black/40">
      <div className="flex justify-between mb-2">
        <span className="text-gray-400 text-sm">{label}</span>
        <span className={`${paused ? 'text-red-400' : 'text-white'} font-mono text-sm`}>
          {used}/{limit} {paused && '(PAUSED)'}
        </span>
      </div>
      <div className="w-full bg-gray-900 rounded-full h-2">
        <div 
          className={`${color} h-2 rounded-full transition-all duration-500`} 
          style={{ width: `${percentage}%` }}
        ></div>
      </div>
    </div>
  );
};

export const WarChestDashboard = () => {
  const [quotas, setQuotas] = useState({});
  const [heartbeat, setHeartbeat] = useState('healthy');
  const [loading, setLoading] = useState(true);

  // Simulated API fetch from the Governor
  useEffect(() => {
    const fetchQuotas = async () => {
      // In production: const res = await axios.get('/api/governor/status');
      // setQuotas(res.data);
      setQuotas({
        shodan: { used: 45, limit: 100, paused: false },
        censys: { used: 12, limit: 50, paused: false },
        virustotal: { used: 490, limit: 500, paused: true },
        binaryedge: { used: 5, limit: 250, paused: false },
      });
      setLoading(false);
    };
    fetchQuotas();
    const interval = setInterval(fetchQuotas, 10000);
    return () => clearInterval(interval);
  }, []);

  const handleFlashScan = () => {
    console.log("Triggering high-priority Flash Scan...");
    // Call backend manual override
  };

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-6 bg-[#0a0a0a] text-white min-h-screen">
      {/* Header */}
      <div className="flex justify-between items-center border-b border-gray-800 pb-4">
        <div className="flex items-center gap-3">
          <Shield className="text-blue-500 w-8 h-8" />
          <h1 className="text-2xl font-bold tracking-tight">K1 API WAR CHEST</h1>
        </div>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2 px-3 py-1 bg-green-950/30 border border-green-900 rounded-full">
            <Activity className="w-4 h-4 text-green-500 animate-pulse" />
            <span className="text-xs text-green-400 font-mono">GOVERNOR: {heartbeat.toUpperCase()}</span>
          </div>
          <button 
            onClick={handleFlashScan}
            className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 px-4 py-2 rounded-md font-bold transition-colors text-sm"
          >
            <Zap className="w-4 h-4 fill-current" />
            FLASH SCAN
          </button>
        </div>
      </div>

      {/* Quota Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {Object.entries(quotas).map(([provider, data]) => (
          <Gauge 
            key={provider}
            label={provider.toUpperCase()} 
            used={data.used} 
            limit={data.limit}
            paused={data.paused}
          />
        ))}
      </div>

      {/* Schedule & Logs */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Timeline View */}
        <div className="lg:col-span-2 border border-gray-800 rounded-lg p-4 bg-black/40">
          <div className="flex items-center gap-2 mb-4">
            <Clock className="w-5 h-5 text-gray-400" />
            <h2 className="font-bold">24-HOUR SCAN TIMELINE</h2>
          </div>
          <div className="h-48 flex items-end gap-1 px-2 border-b border-gray-800">
            {/* Simple Histogram Simulation */}
            {Array.from({ length: 24 }).map((_, i) => {
              const isPeak = i === 6; // 6 AM MST
              return (
                <div 
                  key={i} 
                  className={`flex-1 ${isPeak ? 'bg-blue-500' : 'bg-gray-800'} rounded-t-sm hover:bg-blue-400 transition-colors cursor-pointer group relative`}
                  style={{ height: `${isPeak ? 90 : Math.random() * 40 + 10}%` }}
                >
                  <div className="absolute -top-8 left-1/2 -translate-x-1/2 bg-gray-900 text-[10px] px-1 rounded opacity-0 group-hover:opacity-100 whitespace-nowrap">
                    {i}:00 - {isPeak ? 'RESET PEAK' : 'DRIP'}
                  </div>
                </div>
              );
            })}
          </div>
          <div className="flex justify-between mt-2 text-[10px] text-gray-500 font-mono">
            <span>00:00 UTC</span>
            <span>06:00 MST</span>
            <span>12:00</span>
            <span>18:00</span>
            <span>23:59</span>
          </div>
        </div>

        {/* Key Management */}
        <div className="border border-gray-800 rounded-lg p-4 bg-black/40">
          <div className="flex items-center gap-2 mb-4">
            <Key className="w-5 h-5 text-gray-400" />
            <h2 className="font-bold">WAR CHEST SECRETS</h2>
          </div>
          <div className="space-y-3">
            {['SHODAN', 'CENSYS', 'VT'].map(key => (
              <div key={key} className="flex justify-between items-center p-2 bg-gray-900/50 rounded border border-gray-800">
                <span className="text-xs text-gray-400">{key}</span>
                <span className="text-xs font-mono">sk-•••••4291</span>
                <RefreshCw className="w-3 h-3 text-gray-600 hover:text-blue-400 cursor-pointer" />
              </div>
            ))}
            <button className="w-full mt-4 py-2 border border-dashed border-gray-700 rounded text-xs text-gray-500 hover:border-blue-500 hover:text-blue-400 transition-all">
              + ADD NEW CREDENTIAL
            </button>
          </div>
        </div>
      </div>

      {/* System Alerts */}
      <div className="flex items-center gap-3 p-4 bg-orange-950/20 border border-orange-900/50 rounded-lg text-orange-200">
        <AlertTriangle className="w-5 h-5 flex-shrink-0" />
        <p className="text-sm">
          <span className="font-bold uppercase mr-2">Warning:</span>
          VirusTotal daily quota reached. Failover active. 12 tasks rescheduled for 00:00 UTC reset.
        </p>
      </div>
    </div>
  );
};
