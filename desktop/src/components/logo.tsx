import { cn } from "@/lib/cn";

type Props = {
  className?: string;
  /** Pixel size for the bounding box. Defaults to 16 (nav rail). */
  size?: number;
  title?: string;
};

/**
 * LuckyResume logo — a bold capital "L" anchoring a four-leaf clover
 * tucked into the upper-right corner. The L reads as a wordmark anchor;
 * the clover carries the "lucky" theme without leaning on text.
 *
 * Both shapes are filled with `currentColor`, so the icon inherits the
 * theme accent or any text color the parent sets — no SVG palette to
 * keep in sync with the theme. Designed to stay legible down to 16 px,
 * the size used in the nav rail.
 */
export function Logo({ className, size = 16, title = "LuckyResume" }: Props) {
  return (
    <svg
      role="img"
      aria-label={title}
      viewBox="0 0 24 24"
      width={size}
      height={size}
      fill="currentColor"
      className={cn("shrink-0", className)}
    >
      <title>{title}</title>
      {/* Capital L — vertical stroke + base. Slight inner-corner radius
          via a single path so the L reads as one shape, not two rects. */}
      <path d="M4.5 4 H7.5 V17 H17 V20 H4.5 Z" />
      {/* Four-leaf clover, diamond layout, in the L's negative space.
          Each leaf is ~2 px radius at 24-unit viewBox; small enough to
          stay distinct from the L stroke at any render size. */}
      <circle cx="16" cy="6" r="1.9" />
      <circle cx="12.6" cy="9.4" r="1.9" />
      <circle cx="19.4" cy="9.4" r="1.9" />
      <circle cx="16" cy="12.8" r="1.9" />
      {/* Stem joining the clover quartet — half-opacity so it visually
          recedes and the four leaves stay primary. */}
      <rect x="15.4" y="12.5" width="1.2" height="3.5" rx="0.4" opacity="0.55" />
    </svg>
  );
}
