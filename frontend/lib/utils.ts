// Utility belt for the entire frontend.
// cn() merges Tailwind classes, eliminating conflicts — the standard pattern used by shadcn/ui
import { type ClassValue, clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

// formatCurrency: formats paise (backend integer unit) to rupee display strings.
// Backend stores money as integers (e.g. 2450000 = ₹24,500.00) to avoid floating-point errors.
export function formatCurrency(paise: number, currency = 'INR'): string {
  const amount = paise / 100;
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency,
    minimumFractionDigits: 2,
  }).format(amount);
}

// formatCurrencyFromFloat: for API responses that return balance as float directly
export function formatCurrencyFromFloat(amount: number, currency = 'INR'): string {
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency,
    minimumFractionDigits: 2,
  }).format(amount);
}

// formatDate: human-readable date in Indian locale
export function formatDate(iso: string): string {
  return new Intl.DateTimeFormat('en-IN', {
    year: 'numeric', month: 'short', day: 'numeric',
  }).format(new Date(iso));
}

// formatRelativeTime: "2 hours ago", "Yesterday", etc.
export function formatRelativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) return 'just now';
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days === 1) return 'Yesterday';
  if (days < 7) return `${days} days ago`;
  return formatDate(iso);
}

// truncate: safe string truncation with ellipsis for UI labels
export function truncate(str: string, length: number): string {
  return str.length > length ? `${str.slice(0, length)}…` : str;
}

// groupBy: generic array grouping utility used in conversation list (Today / Yesterday / Last Week)
export function groupBy<T>(arr: T[], key: (item: T) => string): Record<string, T[]> {
  return arr.reduce((acc, item) => {
    const k = key(item);
    if (!acc[k]) acc[k] = [];
    acc[k].push(item);
    return acc;
  }, {} as Record<string, T[]>);
}

// getConversationDateGroup: ChatGPT-style date grouping
export function getConversationDateGroup(iso: string): string {
  const date = new Date(iso);
  const now = new Date();
  const diff = Math.floor((now.getTime() - date.getTime()) / 86400000);
  if (diff === 0) return 'Today';
  if (diff === 1) return 'Yesterday';
  if (diff < 7) return 'Last 7 Days';
  if (diff < 30) return 'Last Month';
  return 'Older';
}

// getInitials: avatar fallback from user name
export function getInitials(name: string): string {
  return name.split(' ').map(n => n[0]).slice(0, 2).join('').toUpperCase();
}
