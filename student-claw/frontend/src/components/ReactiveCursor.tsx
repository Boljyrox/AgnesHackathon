"use client";

/**
 * Reactive cursor — a glowing sky-neon orb that trails the mouse with spring
 * physics and magnetically snaps to elements marked `data-magnetic` (buttons,
 * links). Additive overlay (pointer-events-none) so the native cursor stays for
 * usability. Auto-disabled on touch devices via CSS.
 */

import { motion, useMotionValue, useSpring } from "framer-motion";
import { useEffect, useState } from "react";

export function ReactiveCursor() {
  const x = useMotionValue(-100);
  const y = useMotionValue(-100);
  const sx = useSpring(x, { stiffness: 350, damping: 28, mass: 0.4 });
  const sy = useSpring(y, { stiffness: 350, damping: 28, mass: 0.4 });
  const [hovering, setHovering] = useState(false);

  useEffect(() => {
    function onMove(e: PointerEvent) {
      const target = (e.target as HTMLElement | null)?.closest<HTMLElement>(
        "[data-magnetic], a, button",
      );
      if (target) {
        // Magnetic snap to the element centre.
        const r = target.getBoundingClientRect();
        x.set(r.left + r.width / 2);
        y.set(r.top + r.height / 2);
        setHovering(true);
      } else {
        x.set(e.clientX);
        y.set(e.clientY);
        setHovering(false);
      }
    }
    window.addEventListener("pointermove", onMove, { passive: true });
    return () => window.removeEventListener("pointermove", onMove);
  }, [x, y]);

  return (
    <motion.div
      aria-hidden
      className="reactive-cursor pointer-events-none fixed left-0 top-0 z-[100] hidden lg:block"
      style={{ x: sx, y: sy }}
    >
      <motion.div
        className="-translate-x-1/2 -translate-y-1/2 rounded-full"
        animate={{
          width: hovering ? 56 : 22,
          height: hovering ? 56 : 22,
          opacity: hovering ? 0.35 : 0.6,
        }}
        transition={{ type: "spring", stiffness: 300, damping: 24 }}
        style={{
          background:
            "radial-gradient(circle, rgba(56,189,248,0.9) 0%, rgba(56,189,248,0.25) 55%, transparent 75%)",
          boxShadow: "0 0 40px 8px rgba(56,189,248,0.35)",
        }}
      />
    </motion.div>
  );
}
