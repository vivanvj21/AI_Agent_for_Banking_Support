// next-themes ThemeProvider re-export.
// We wrap it here (instead of importing directly in layout) so that:
// 1. We can add custom theme logic later without touching layout.tsx
// 2. It's clearly co-located with other providers
'use client';
import { ThemeProvider as NextThemesProvider } from 'next-themes';
import type { ThemeProviderProps } from 'next-themes';

export function ThemeProvider({ children, ...props }: ThemeProviderProps) {
  return <NextThemesProvider {...props}>{children}</NextThemesProvider>;
}
