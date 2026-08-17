// Root layout — establishes the provider hierarchy for the entire app.
// Providers are ordered from most-stable (ThemeProvider) to most-reactive (ToastProvider)
// to minimize unnecessary re-renders from outer context changes.
import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import { GeistSans } from 'geist/font/sans';
import { GeistMono } from 'geist/font/mono';
import { cn } from '@/lib/utils';
import './globals.css';

import { ThemeProvider } from '@/components/providers/ThemeProvider';
import { QueryProvider } from '@/components/providers/QueryProvider';
import { AuthProvider } from '@/components/providers/AuthProvider';
import { Toaster } from 'sonner';

const inter = Inter({
  subsets: ['latin'],
  variable: '--font-inter',
  display: 'swap',
});

export const metadata: Metadata = {
  title: {
    default: 'Nexus Banking — AI-First Banking Platform',
    template: '%s | Nexus Banking',
  },
  description: 'Autonomous AI banking assistant with multi-agent intelligence, real-time fraud detection, and intelligent account management.',
  keywords: ['AI banking', 'autonomous assistant', 'fraud detection', 'LangGraph', 'fintech'],
  robots: { index: false }, // Private banking app — not for public indexing
  icons: { icon: '/favicon.ico' },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning className={cn(GeistSans.variable, GeistMono.variable, inter.variable)}>
      <body className={cn('min-h-screen bg-background font-sans antialiased')}>
        {/* ThemeProvider wraps everything — must be outermost to prevent flash of unstyled content */}
        <ThemeProvider attribute="class" defaultTheme="dark" enableSystem={false} disableTransitionOnChange={false}>
          <QueryProvider>
            <AuthProvider>
              {children}
              {/* Sonner toast portal — renders outside component tree for correct z-index stacking */}
              <Toaster
                position="bottom-right"
                theme="dark"
                richColors
                closeButton
                toastOptions={{
                  style: {
                    background: 'hsl(222 37% 12%)',
                    border: '1px solid hsl(222 25% 18%)',
                    color: 'hsl(0 0% 97%)',
                  },
                }}
              />
            </AuthProvider>
          </QueryProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
