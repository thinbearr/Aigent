/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // synchronized.studio-inspired: near-black, white, one pale-green accent.
        canvas: "#0b0b0c",
        card: "#131315",
        line: "#272729",
        ink: "#f4f4f2",
        sub: "#9a9a9c",
        faint: "#67676a",
        iris: "#deebc8",     // pale-green accent (the agent / Blue identity)
        iris2: "#cbdfaa",
        mint: "#5fd39a",
        amber: "#f0b44a",
        rose: "#f2537a",
        sky: "#6bb6ff",
        blue: { blue: "#3b82f6" },
      },
      fontFamily: {
        sans: ["'Space Grotesk'", "Inter", "system-ui", "sans-serif"],
        mono: ["'JetBrains Mono'", "ui-monospace", "monospace"],
      },
      boxShadow: {
        soft: "0 1px 2px rgba(0,0,0,0.5), 0 18px 50px -24px rgba(0,0,0,0.8)",
        lift: "0 2px 6px rgba(0,0,0,0.5), 0 24px 60px -24px rgba(0,0,0,0.9)",
        glow: "0 0 0 4px rgba(222,235,200,0.12)",
      },
      keyframes: {
        rise: { "0%": { opacity: "0", transform: "translateY(10px)" }, "100%": { opacity: "1", transform: "translateY(0)" } },
        pop: { "0%": { opacity: "0", transform: "scale(0.96)" }, "100%": { opacity: "1", transform: "scale(1)" } },
        shimmer: { "0%": { backgroundPosition: "-200% 0" }, "100%": { backgroundPosition: "200% 0" } },
        orbit: { "0%": { transform: "rotate(0deg)" }, "100%": { transform: "rotate(360deg)" } },
        breathe: { "0%,100%": { transform: "scale(1)", opacity: "0.8" }, "50%": { transform: "scale(1.08)", opacity: "1" } },
        fadeout: { "0%": { opacity: "1" }, "100%": { opacity: "0", visibility: "hidden" } },
      },
      animation: {
        rise: "rise .5s cubic-bezier(.2,.7,.2,1) both",
        pop: "pop .3s ease both",
        shimmer: "shimmer 1.6s linear infinite",
        orbit: "orbit 3s linear infinite",
        breathe: "breathe 2.4s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};
