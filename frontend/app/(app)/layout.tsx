// Protected app layout — wraps all authenticated pages with AppShell.
import { AppShell } from '@/components/layout/AppShell';

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return <AppShell>{children}</AppShell>;
}
