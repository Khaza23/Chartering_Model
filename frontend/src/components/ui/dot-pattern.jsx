import React, { useId } from 'react';
import { cn } from '../../lib/utils';

/**
 * DotPattern — tiled SVG dot grid (shadcn-style).
 *
 * Adapted from `dot-pattern.tsx` to plain JSX so it runs in this
 * Vite + JS codebase (no Tailwind / TypeScript required). Same props API
 * as the original; JSDoc below replaces the `DotPatternProps` interface.
 *
 * Tailwind notes (no Tailwind installed here):
 * - Layout classes (`absolute inset-0 h-full w-full pointer-events-none`)
 *   are reproduced as inline styles so the component works standalone.
 * - `fill-neutral-400/80` is replaced with `currentColor` + the
 *   `.dot-pattern` CSS class (`color: var(--ink-subtle)`, opacity ~0.5),
 *   so dots follow the App.css light/dark theme automatically.
 * - Vite has no `@` alias configured, hence the relative utils import.
 *   If shadcn CLI is run later, switch to `@/lib/utils` + `@/components/ui`.
 *
 * @param {number} [width=16] Pattern tile width in px
 * @param {number} [height=16] Pattern tile height in px
 * @param {number} [x=0] Pattern x offset
 * @param {number} [y=0] Pattern y offset
 * @param {number} [cx=1] Dot centre x within a tile
 * @param {number} [cy=1] Dot centre y within a tile
 * @param {number} [cr=1] Dot radius
 * @param {string} [className] Extra class names (merged via cn)
 * @param {object} [style] Extra inline styles (merged, wins over defaults)
 */
export function DotPattern({
  width = 16,
  height = 16,
  x = 0,
  y = 0,
  cx = 1,
  cy = 1,
  cr = 1,
  className,
  style,
  ...props
}) {
  const id = useId();

  return (
    <svg
      aria-hidden="true"
      className={cn('dot-pattern', className)}
      style={{
        position: 'absolute',
        inset: 0,
        height: '100%',
        width: '100%',
        pointerEvents: 'none',
        ...style,
      }}
      {...props}
    >
      <defs>
        <pattern
          id={id}
          width={width}
          height={height}
          patternUnits="userSpaceOnUse"
          patternContentUnits="userSpaceOnUse"
          x={x}
          y={y}
        >
          <circle id="pattern-circle" cx={cx} cy={cy} r={cr} />
        </pattern>
      </defs>
      <rect width="100%" height="100%" strokeWidth={0} fill={`url(#${id})`} />
    </svg>
  );
}

export default DotPattern;
