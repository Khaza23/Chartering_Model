import React from 'react';
import { motion } from 'framer-motion';

/**
 * GradientDots — animated hexagonal dot-mask over shifting gradients.
 *
 * Adapted from the shadcn-style `gradient-dots.tsx` to plain JSX so it runs
 * in this Vite + JS codebase (no Tailwind / TypeScript required).
 * Once TypeScript is enabled, rename to `.tsx` and restore the prop types
 * (see JSDoc below — same API).
 *
 * @param {number} [dotSize=8] Dot mask radius in px
 * @param {number} [spacing=10] Spacing between dots in px
 * @param {number} [duration=30] Background-pan duration in seconds
 * @param {number} [colorCycleDuration=6] Hue-rotate duration in seconds
 * @param {string} [backgroundColor] Dot cutout colour — defaults to `var(--canvas)` so it matches App.css light/dark theme
 * @param {string} [className] Extra class names
 */
export function GradientDots({
  dotSize = 8,
  spacing = 10,
  duration = 30,
  colorCycleDuration = 6,
  backgroundColor = 'var(--canvas)',
  className = '',
  style,
  ...props
}) {
  const hexSpacing = spacing * 1.732; // Hexagonal row spacing
  const halfX = spacing / 2;
  const halfY = hexSpacing / 2;

  // 6 background layers = 6 sizes + 6 positions (original snippet shipped 5 positions — fixed here).
  const dotLayerA = `0px 0px`;
  const dotLayerB = `${halfX}px ${halfY}px`;

  return (
    <motion.div
      aria-hidden="true"
      className={`gradient-dots ${className}`.trim()}
      style={{
        position: 'absolute',
        inset: 0,
        overflow: 'hidden',
        backgroundColor,
        backgroundImage: `
          radial-gradient(circle at 50% 50%, transparent 1.5px, ${backgroundColor} 0 ${dotSize}px, transparent ${dotSize}px),
          radial-gradient(circle at 50% 50%, transparent 1.5px, ${backgroundColor} 0 ${dotSize}px, transparent ${dotSize}px),
          radial-gradient(circle at 50% 50%, #f00, transparent 60%),
          radial-gradient(circle at 50% 50%, #ff0, transparent 60%),
          radial-gradient(circle at 50% 50%, #0f0, transparent 60%),
          radial-gradient(ellipse at 50% 50%, #00f, transparent 60%)
        `,
        backgroundSize: `
          ${spacing}px ${hexSpacing}px,
          ${spacing}px ${hexSpacing}px,
          200% 200%,
          200% 200%,
          200% 200%,
          200% 200%
        `,
        backgroundPosition: `
          ${dotLayerA},
          ${dotLayerB},
          0% 0%,
          0% 0%,
          0% 0%,
          0% 0%
        `,
        ...style,
      }}
      animate={{
        backgroundPosition: [
          `${dotLayerA}, ${dotLayerB}, 800% 400%, 1000% -400%, -1200% -600%, 400% 200%`,
          `${dotLayerA}, ${dotLayerB}, 0% 0%, 0% 0%, 0% 0%, 0% 0%`,
        ],
        filter: ['hue-rotate(0deg)', 'hue-rotate(360deg)'],
      }}
      transition={{
        backgroundPosition: {
          duration,
          ease: 'linear',
          repeat: Number.POSITIVE_INFINITY,
        },
        filter: {
          duration: colorCycleDuration,
          ease: 'linear',
          repeat: Number.POSITIVE_INFINITY,
        },
      }}
      {...props}
    />
  );
}

export default GradientDots;
