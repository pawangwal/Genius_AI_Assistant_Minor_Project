import React, { useState, useEffect } from 'react';
import { Cpu, MemoryStick as Memory, Clock, Wifi, CircleOff, AlertTriangle } from 'lucide-react';
import { fetchNetworkStatus, NetworkStatusResponse } from '../services/api';

const SystemStatusCards: React.FC = () => {
  const [time, setTime] = useState(new Date());
  const [cpuUsage, setCpuUsage] = useState(14);
  const [memoryUsage, setMemoryUsage] = useState(48);
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

  // Simulate local CPU & Memory telemetry
  useEffect(() => {
    const updateMetrics = () => {
      setCpuUsage(Math.floor(12 + Math.random() * 18));
      setMemoryUsage(Math.floor(45 + Math.random() * 10));
    };

    const interval = setInterval(updateMetrics, 4000);
    return () => clearInterval(interval);
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

  // Resolve Network card visual properties
  const getNetworkCardProps = () => {
    switch (networkStatus.status) {
      case 'connected':
        return {
          icon: <Wifi size={16} />,
          value: 'Connected',
          detail: `${networkStatus.provider.toUpperCase()} (${networkStatus.model.split('/')[1] || networkStatus.model})`,
          color: 'green' as const,
        };
      case 'degraded':
        return {
          icon: <AlertTriangle size={16} />,
          value: 'Degraded',
          detail: networkStatus.detail,
          color: 'amber' as const,
        };
      case 'offline':
        return {
          icon: <CircleOff size={16} />,
          value: 'Offline',
          detail: networkStatus.detail,
          color: 'red' as const,
        };
      case 'checking':
      default:
        return {
          icon: <Wifi size={16} className="animate-pulse" />,
          value: 'Checking...',
          detail: 'Connecting to AI provider...',
          color: 'cyan' as const,
        };
    }
  };

  const netCard = getNetworkCardProps();

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-4 gap-3 w-full">
      <StatusCard
        icon={<Clock size={16} />}
        title="System Time"
        value={time.toLocaleTimeString()}
        detail={time.toLocaleDateString()}
        color="cyan"
      />

      <StatusCard
        icon={<Cpu size={16} />}
        title="CPU Usage"
        value={`${cpuUsage}%`}
        detail={cpuUsage > 25 ? 'High Activity' : 'Normal Load'}
        color={cpuUsage > 25 ? 'amber' : 'green'}
      />

      <StatusCard
        icon={<Memory size={16} />}
        title="Memory"
        value={`${memoryUsage}%`}
        detail={`${((16 * memoryUsage) / 100).toFixed(1)}GB / 16GB`}
        color={memoryUsage > 50 ? 'amber' : 'green'}
      />

      <StatusCard
        icon={netCard.icon}
        title="Network"
        value={netCard.value}
        detail={netCard.detail}
        color={netCard.color}
        tooltip={networkStatus.detail}
      />
    </div>
  );
};

interface StatusCardProps {
  icon: React.ReactNode;
  title: string;
  value: string;
  detail: string;
  color: 'cyan' | 'green' | 'amber' | 'red';
  tooltip?: string;
}

const StatusCard: React.FC<StatusCardProps> = ({ icon, title, value, detail, color, tooltip }) => {
  const getColorClasses = () => {
    switch (color) {
      case 'cyan':
        return 'from-cyan-900/40 to-blue-900/40 border-cyan-800 text-cyan-400';
      case 'green':
        return 'from-emerald-900/40 to-green-900/40 border-emerald-800 text-emerald-400';
      case 'amber':
        return 'from-amber-900/40 to-orange-900/40 border-amber-800 text-amber-400';
      case 'red':
        return 'from-red-900/40 to-rose-900/40 border-red-800 text-red-400';
      default:
        return 'from-cyan-900/40 to-blue-900/40 border-cyan-800 text-cyan-400';
    }
  };

  return (
    <div
      title={tooltip || detail}
      className={`p-3 rounded-lg bg-gradient-to-br ${getColorClasses()} backdrop-blur-md border border-opacity-50 shadow-lg transition-all`}
    >
      <div className="flex items-center mb-1">
        <div className="mr-2">{icon}</div>
        <div className="text-xs font-semibold opacity-80">{title}</div>
      </div>
      <div className="font-mono text-lg font-bold truncate">{value}</div>
      <div className="text-xs opacity-70 truncate">{detail}</div>
    </div>
  );
};

export default SystemStatusCards;