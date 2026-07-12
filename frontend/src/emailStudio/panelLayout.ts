/**
 * Panel layout state for the Email Design Studio: persisted, clamped
 * widths and open/closed flags for the left (variables/presets) panel
 * and the preview panel. Kept React-free where possible so the clamp
 * logic is unit-testable.
 */
import { useState } from 'react';

export const LEFT_PANEL = { min: 200, max: 520, initial: 280 };
export const PREVIEW_PANEL = { min: 300, max: 900, initial: 480 };

export const clampWidth = (
  value: number,
  bounds: { min: number; max: number }
): number => Math.min(bounds.max, Math.max(bounds.min, value));

export function usePersistentState<T>(
  key: string,
  initial: T
): [T, (value: T) => void] {
  const [value, setValue] = useState<T>(() => {
    try {
      const raw = localStorage.getItem(key);
      return raw !== null ? (JSON.parse(raw) as T) : initial;
    } catch {
      return initial;
    }
  });
  const set = (next: T) => {
    setValue(next);
    try {
      localStorage.setItem(key, JSON.stringify(next));
    } catch {
      // Persistence is best-effort; never break the UI over storage.
    }
  };
  return [value, set];
}

/**
 * Start a horizontal drag-resize. `direction` is +1 when dragging right
 * grows the panel (left-side panels) and -1 when dragging right shrinks
 * it (right-side panels).
 */
export const startPanelDrag = (
  startClientX: number,
  startWidth: number,
  direction: 1 | -1,
  bounds: { min: number; max: number },
  onResize: (width: number) => void
) => {
  const onMove = (event: MouseEvent) => {
    const delta = (event.clientX - startClientX) * direction;
    onResize(clampWidth(startWidth + delta, bounds));
  };
  const onUp = () => {
    window.removeEventListener('mousemove', onMove);
    window.removeEventListener('mouseup', onUp);
    document.body.style.removeProperty('cursor');
    document.body.style.removeProperty('user-select');
  };
  window.addEventListener('mousemove', onMove);
  window.addEventListener('mouseup', onUp);
  document.body.style.cursor = 'col-resize';
  document.body.style.userSelect = 'none';
};
