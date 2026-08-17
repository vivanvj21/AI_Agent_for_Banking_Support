// AnimatedCounter — spring-animated number that counts up from 0 to target.
// Used for balances, transaction counts, and metrics.
// The spring physics feel more premium than a linear tween.
'use client';
import { useEffect, useRef, useState } from 'react';
import { useInView } from 'framer-motion';

interface AnimatedCounterProps {
  value: number;
  prefix?: string;
  suffix?: string;
  decimals?: number;
  duration?: number;
  className?: string;
}

export function AnimatedCounter({
  value,
  prefix = '',
  suffix = '',
  decimals = 0,
  duration = 1200,
  className,
}: AnimatedCounterProps) {
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true });
  const [displayed, setDisplayed] = useState(0);

  useEffect(() => {
    if (!inView) return;
    let start = 0;
    const startTime = performance.now();

    const animate = (now: number) => {
      const elapsed = now - startTime;
      const progress = Math.min(elapsed / duration, 1);
      // Ease-out cubic
      const eased = 1 - Math.pow(1 - progress, 3);
      setDisplayed(eased * value);
      if (progress < 1) requestAnimationFrame(animate);
    };

    requestAnimationFrame(animate);
  }, [inView, value, duration]);

  return (
    <span ref={ref} className={className}>
      {prefix}{displayed.toFixed(decimals)}{suffix}
    </span>
  );
}
