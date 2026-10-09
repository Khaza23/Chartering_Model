/**
 * cn() — minimal class-name joiner (shadcn-style).
 *
 * The full shadcn `cn` is `twMerge(clsx(...))`, but this codebase has no
 * Tailwind dependency, so conditional merging is unnecessary. This joins
 * truthy segments with a single space — same call signature, zero deps.
 * If Tailwind is added later, replace the body with:
 *   import { clsx } from "clsx";
 *   import { twMerge } from "tailwind-merge";
 *   export function cn(...inputs) { return twMerge(clsx(inputs)); }
 */
export function cn(...inputs) {
  return inputs.flat(Infinity).filter(Boolean).join(" ");
}

export default cn;
