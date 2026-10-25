import React, { useState, useEffect } from 'react';
import { Clock, Wifi, CircleOff, AlertTriangle } from 'lucide-react';
import { fetchNetworkStatus, NetworkStatusResponse } from '../services/api';

const SystemStatusCards: React.FC = () => {
  const [time, setTime] = useState(new Date());
  const [networkStatus, setNetworkStatus] = useState<NetworkStatusResponse>({
    fastapi: 'online',
    provider: 'checking',
    status: 'checking',
    detail: 'Verifying AI provider connectivity...',
    model: 'loading...',
  });

  // Update clock every second
  useEffect(() => {
    const timer = setInterval(() => {
      setTime(new Date());
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  // Real LLM Provider & Network polling
  useEffect(() => {
    let isCancelled = false;

    const pollNetwork = async () => {
      try {
        const data = await fetchNetworkStatus();
        if (!isCancelled) {
          setNetworkStatus(data);
        }
      } catch {
        if (!isCancelled) {
          setNetworkStatus({
            fastapi: 'offline',
            provider: 'unknown',
            status: 'offline',
            detail: 'Backend server unreachable (http://127.0.0.1:8000)',
            model: 'none',
          });
        }
      }
    };

    pollNetwork();
    const interval = setInterval(pollNetwork, 10000); // 10s polling

    return () => {
      isCancelled = true;
      clearInterval(interval);
    };
  }, []);

  // Resolve Network status visual properties
  const getNetworkProps = () => {
    switch (networkStatus.status) {
      case 'connected':
        return {
          icon: <Wifi size={14} className="text-emerald-400" />,
          label: 'Connected',
          badgeColor: 'bg-emerald-950/80 border-emerald-700/60 text-emerald-300',
          dotColor: 'bg-emerald-400',
          providerText: `${networkStatus.provider.toUpperCase()} (${networkStatus.model.split('/')[1] || networkStatus.model})`,
        };
      case 'degraded':
        return {
          icon: <AlertTriangle size={14} className="text-amber-400" />,
          label: 'Degraded',
          badgeColor: 'bg-amber-950/80 border-amber-700/60 text-amber-300',
          dotColor: 'bg-amber-400',
          providerText: networkStatus.detail,
        };
      case 'offline':
        return {
          icon: <CircleOff size={14} className="text-rose-400" />,
          label: 'Offline',
          badgeColor: 'bg-rose-950/80 border-rose-700/60 text-rose-300',
          dotColor: 'bg-rose-400',
          providerText: networkStatus.detail,
        };
      case 'checking':
      default:
        return {
          icon: <Wifi size={14} className="text-cyan-400 animate-pulse" />,
          label: 'Checking...',
          badgeColor: 'bg-cyan-950/80 border-cyan-700/60 text-cyan-300',
          dotColor: 'bg-cyan-400 animate-ping',
          providerText: 'Connecting to AI provider...',
        };
    }
  };

  const netProps = getNetworkProps();

  return (
    <div className="w-full flex flex-wrap items-center justify-between gap-3 px-4 py-2.5 rounded-xl bg-gray-950/60 border border-cyan-900/40 backdrop-blur-md shadow-lg text-xs">
      {/* System Time Section */}
      <div className="flex items-center space-x-3">
        <div className="flex items-center space-x-2 text-cyan-400 font-semibold tracking-wider">
          <Clock size={15} className="text-cyan-400 shrink-0" />
          <span className="text-[11px] text-cyan-500 uppercase font-mono">System Time</span>
        </div>
        <div className="flex items-center space-x-2">
          <span className="font-mono text-sm font-bold text-gray-100">
            {time.toLocaleTimeString()}
          </span>
          <span className="text-[11px] text-gray-400 font-mono hidden sm:inline px-2 py-0.5 rounded bg-cyan-950/40 border border-cyan-900/40">
            {time.toLocaleDateString([], { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' })}
          </span>
        </div>
      </div>

      {/* Network & Provider Status Section */}
      <div 
        className="flex items-center space-x-2.5"
        title={networkStatus.detail}
      >
        <div className="flex items-center space-x-1.5 text-gray-400 text-[11px] uppercase font-mono hidden md:inline-flex">
          <span>AI Network</span>
        </div>

        <div className={`flex items-center space-x-2 px-2.5 py-1 rounded-lg border ${netProps.badgeColor} transition-all shadow-sm`}>
          <span className="relative flex h-2 w-2">
            <span className={`absolute inline-flex h-full w-full rounded-full opacity-75 ${netProps.dotColor}`} />
            <span className={`relative inline-flex rounded-full h-2 w-2 ${netProps.dotColor}`} />
          </span>
          {netProps.icon}
          <span className="font-semibold text-xs">{netProps.label}</span>
          <span className="text-gray-400 text-[10px] hidden sm:inline font-mono">
            • {netProps.providerText}
          </span>
        </div>
      </div>
    </div>
  );
};

export default SystemStatusCards;