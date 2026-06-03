import { type ClassValue, clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  const secs = seconds % 60;
  if (minutes < 60) return `${minutes}m ${secs}s`;
  const hours = Math.floor(minutes / 60);
  const mins = minutes % 60;
  return `${hours}h ${mins}m`;
}

export function formatUptime(seconds: number): string {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = seconds % 60;
  return `${hours}h ${minutes}m ${secs}s`;
}

export function formatTime(isoString: string): string {
  try {
    const date = new Date(isoString);
    return date.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  } catch {
    return '--:--:--';
  }
}

export function formatRelativeTime(isoString: string): string {
  try {
    const diff = Date.now() - new Date(isoString).getTime();
    const minutes = Math.floor(diff / 60000);
    if (minutes < 1) return 'Just now';
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}h ago`;
    return `${Math.floor(hours / 24)}d ago`;
  } catch {
    return '--';
  }
}

export function getConfidenceLevel(confidence: number): 'high' | 'medium' | 'low' {
  if (confidence >= 0.85) return 'high';
  if (confidence >= 0.65) return 'medium';
  return 'low';
}

export function getConfidenceColor(confidence: number): string {
  if (confidence >= 0.85) return 'text-green-400';
  if (confidence >= 0.65) return 'text-amber-400';
  return 'text-red-400';
}

export function getSeverityColor(severity: string): string {
  switch (severity.toUpperCase()) {
    case 'HIGH': return 'text-red-400';
    case 'MEDIUM': return 'text-amber-400';
    case 'LOW': return 'text-blue-400';
    default: return 'text-gray-400';
  }
}

export function formatPct(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}
