"use client";

import { motion, useReducedMotion } from "motion/react";
import type { ReactNode } from "react";

/**
 * Fade-and-rise entrance.
 *
 * `immediate` plays on mount — required for above-the-fold content, where
 * waiting on IntersectionObserver is fragile (headless browsers, crawlers,
 * low-power devices). Everything below the fold animates when scrolled
 * into view, once.
 */
export function Reveal({
  children,
  delay = 0,
  immediate = false,
  className,
}: {
  children: ReactNode;
  delay?: number;
  immediate?: boolean;
  className?: string;
}) {
  const reduce = useReducedMotion();

  if (reduce) {
    return <div className={className}>{children}</div>;
  }

  const visible = { opacity: 1, y: 0 };
  const transition = {
    duration: 0.7,
    delay,
    ease: [0.21, 0.65, 0.26, 1] as const,
  };

  if (immediate) {
    return (
      <motion.div
        className={className}
        initial={{ opacity: 0, y: 24 }}
        animate={visible}
        transition={transition}
      >
        {children}
      </motion.div>
    );
  }

  return (
    <motion.div
      className={className}
      initial={{ opacity: 0, y: 24 }}
      whileInView={visible}
      viewport={{ once: true, margin: "-80px" }}
      transition={transition}
    >
      {children}
    </motion.div>
  );
}
