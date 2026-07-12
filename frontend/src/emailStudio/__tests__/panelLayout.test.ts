/**
 * Unit tests for the studio's panel layout helpers.
 */
import { describe, expect, it, vi } from 'vitest';
import { LEFT_PANEL, PREVIEW_PANEL, clampWidth, startPanelDrag } from '../panelLayout';

describe('clampWidth', () => {
  it('clamps to the panel bounds', () => {
    expect(clampWidth(50, LEFT_PANEL)).toBe(LEFT_PANEL.min);
    expect(clampWidth(9999, LEFT_PANEL)).toBe(LEFT_PANEL.max);
    expect(clampWidth(300, LEFT_PANEL)).toBe(300);
  });
});

describe('startPanelDrag', () => {
  const drag = (clientX: number) =>
    window.dispatchEvent(new MouseEvent('mousemove', { clientX }));
  const release = () => window.dispatchEvent(new MouseEvent('mouseup'));

  it('grows a left panel when dragging right (direction +1)', () => {
    const onResize = vi.fn();
    startPanelDrag(100, 280, 1, LEFT_PANEL, onResize);
    drag(150);
    expect(onResize).toHaveBeenLastCalledWith(330);
    release();
  });

  it('shrinks a right panel when dragging right (direction -1)', () => {
    const onResize = vi.fn();
    startPanelDrag(100, PREVIEW_PANEL.initial, -1, PREVIEW_PANEL, onResize);
    drag(160);
    expect(onResize).toHaveBeenLastCalledWith(PREVIEW_PANEL.initial - 60);
    release();
  });

  it('stops resizing after mouseup and respects bounds while dragging', () => {
    const onResize = vi.fn();
    startPanelDrag(0, 280, 1, LEFT_PANEL, onResize);
    drag(-10_000);
    expect(onResize).toHaveBeenLastCalledWith(LEFT_PANEL.min);
    release();
    onResize.mockClear();
    drag(500);
    expect(onResize).not.toHaveBeenCalled();
  });
});
