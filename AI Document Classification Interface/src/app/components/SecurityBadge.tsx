import { Shield, Lock, AlertTriangle, Eye } from 'lucide-react';

interface SecurityBadgeProps {
  level: 'C0' | 'C1' | 'C2' | 'C3';
  confidence?: number;
  size?: 'sm' | 'md' | 'lg';
  showIcon?: boolean;
}

const levelConfig = {
  C0: {
    label: 'Public',
    description: 'Public Information',
    color: '#60A5FA',
    bgColor: 'bg-blue-100 dark:bg-blue-900/30',
    textColor: 'text-blue-700 dark:text-blue-300',
    borderColor: 'border-blue-300 dark:border-blue-700',
    icon: Eye,
  },
  C1: {
    label: 'Internal',
    description: 'Internal Use Only',
    color: '#FBBF24',
    bgColor: 'bg-amber-100 dark:bg-amber-900/30',
    textColor: 'text-amber-700 dark:text-amber-300',
    borderColor: 'border-amber-300 dark:border-amber-700',
    icon: Shield,
  },
  C2: {
    label: 'Confidential',
    description: 'Confidential',
    color: '#FB923C',
    bgColor: 'bg-orange-100 dark:bg-orange-900/30',
    textColor: 'text-orange-700 dark:text-orange-300',
    borderColor: 'border-orange-300 dark:border-orange-700',
    icon: Lock,
  },
  C3: {
    label: 'Highly Sensitive',
    description: 'Highly Sensitive',
    color: '#EF4444',
    bgColor: 'bg-red-100 dark:bg-red-900/30',
    textColor: 'text-red-700 dark:text-red-300',
    borderColor: 'border-red-300 dark:border-red-700',
    icon: AlertTriangle,
  },
};

const sizeClasses = {
  sm: 'px-2 py-1 text-xs',
  md: 'px-3 py-1.5 text-sm',
  lg: 'px-4 py-2 text-base',
};

export function SecurityBadge({ level, confidence, size = 'md', showIcon = true }: SecurityBadgeProps) {
  // Safety check for undefined level
  const safeLevel = level && levelConfig[level] ? level : 'C0';
  const config = levelConfig[safeLevel];
  const Icon = config.icon;

  return (
    <div className={`inline-flex items-center gap-2 rounded-lg border ${config.bgColor} ${config.textColor} ${config.borderColor} ${sizeClasses[size]} font-medium`}>
      {showIcon && <Icon className="w-4 h-4" />}
      <span>{safeLevel}</span>
      <span className="opacity-75">·</span>
      <span>{config.label}</span>
      {confidence !== undefined && (
        <>
          <span className="opacity-75">·</span>
          <span>{confidence}%</span>
        </>
      )}
    </div>
  );
}
