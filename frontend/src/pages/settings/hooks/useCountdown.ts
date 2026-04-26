import { useState, useEffect } from 'react';

export function useCountdown(seconds: number | null): string {
  const [display, setDisplay] = useState('');

  useEffect(() => {
    if (seconds === null) {
      setDisplay('');
      return;
    }
    const start = Date.now();
    const tick = () => {
      const s = Math.max(0, seconds - Math.floor((Date.now() - start) / 1000));
      const h = Math.floor(s / 3600);
      const m = Math.floor((s % 3600) / 60);
      const sec = s % 60;
      setDisplay(h > 0 ? `${h}h ${m}m` : m > 0 ? `${m}m ${sec}s` : `${sec}s`);
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [seconds]);

  return display;
}
