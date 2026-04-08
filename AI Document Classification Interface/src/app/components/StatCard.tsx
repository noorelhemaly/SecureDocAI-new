import { useEffect, useState, useRef } from 'react';
import { LucideIcon } from 'lucide-react';

interface StatCardProps {
  title: string;
  value: string | number;
  icon: LucideIcon;
  trend?: {
    value: string;
    isPositive: boolean;
  };
  color?: 'blue' | 'teal' | 'green' | 'amber' | 'red';
}

const colorClasses = {
  blue:  'bg-blue-50 dark:bg-blue-900/20 text-[#1E3A8A] dark:text-blue-400',
  teal:  'bg-cyan-50 dark:bg-cyan-900/20 text-[#0891B2] dark:text-cyan-400',
  green: 'bg-green-50 dark:bg-green-900/20 text-[#10B981] dark:text-green-400',
  amber: 'bg-amber-50 dark:bg-amber-900/20 text-[#F59E0B] dark:text-amber-400',
  red:   'bg-red-50 dark:bg-red-900/20 text-[#EF4444] dark:text-red-400',
};

const borderGlow = {
  blue:  { border: '#3B82F6', glow: 'rgba(59,130,246,0.35)' },
  teal:  { border: '#0891B2', glow: 'rgba(8,145,178,0.35)' },
  green: { border: '#10B981', glow: 'rgba(16,185,129,0.35)' },
  amber: { border: '#F59E0B', glow: 'rgba(245,158,11,0.35)' },
  red:   { border: '#EF4444', glow: 'rgba(239,68,68,0.35)' },
};

function useCountUp(target: number, duration = 900) {
  const [count, setCount] = useState(0);
  const raf = useRef<number>(0);
  useEffect(() => {
    if (target <= 0) { setCount(0); return; }
    const start = performance.now();
    const animate = (now: number) => {
      const progress = Math.min((now - start) / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      setCount(Math.round(eased * target));
      if (progress < 1) raf.current = requestAnimationFrame(animate);
    };
    raf.current = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(raf.current);
  }, [target, duration]);
  return count;
}

export function StatCard({ title, value, icon: Icon, trend, color = 'blue' }: StatCardProps) {
  const { border, glow } = borderGlow[color];

  // Parse numeric portion for animation (e.g. "82%" → 82, "142" → 142)
  const rawStr = String(value);
  const numMatch = rawStr.match(/^(\d+)/);
  const numericTarget = numMatch ? parseInt(numMatch[1], 10) : null;
  const suffix = numMatch ? rawStr.slice(numMatch[1].length) : '';
  const isLoading = rawStr === '...' || rawStr === '—';

  const animated = useCountUp(numericTarget ?? 0);
  const displayValue = isLoading
    ? rawStr
    : numericTarget !== null
    ? `${animated}${suffix}`
    : rawStr;

  return (
    <div
      className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-6 hover:shadow-lg transition-all duration-300 border-l-4"
      style={{
        borderLeftColor: border,
        boxShadow: `inset 3px 0 0 ${border}, 0 1px 3px rgba(0,0,0,0.1)`,
      }}
      onMouseEnter={e => (e.currentTarget.style.boxShadow = `inset 3px 0 0 ${border}, 0 4px 20px ${glow}`)}
      onMouseLeave={e => (e.currentTarget.style.boxShadow = `inset 3px 0 0 ${border}, 0 1px 3px rgba(0,0,0,0.1)`)}
    >
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <p className="text-sm text-gray-600 dark:text-gray-400 mb-1">{title}</p>
          <p className="text-3xl font-semibold text-gray-900 dark:text-gray-100 tabular-nums">
            {displayValue}
          </p>
          {trend && (
            <div className="flex items-center gap-1 mt-2">
              <span className={`text-sm ${trend.isPositive ? 'text-green-600' : 'text-red-600'}`}>
                {trend.isPositive ? '↑' : '↓'} {trend.value}
              </span>
              <span className="text-xs text-gray-500 dark:text-gray-400">vs last month</span>
            </div>
          )}
        </div>
        <div className={`p-3 rounded-lg ${colorClasses[color]}`}>
          <Icon className="w-6 h-6" />
        </div>
      </div>
    </div>
  );
}
