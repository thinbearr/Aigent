/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        canvas: "#fbfbfd",
        card: "#ffffff",
        line: "#ececf1",
        ink: "#1a1a2e",
        sub: "#6b6b80",
        faint: "#9a9aad",
        iris: "#5b5bf0",      // signature violet
        iris2: "#7a6cf5",
        mint: "#12b886",
        amber: "#f59f0a",
        rose: "#f43f6e",
        sky: "#2aa7ff",
        blue: { blue: "#3b82f6" },
      },
      fontFamily: {
        sans: ["'Space Grotesk'", "Inter", "system-ui", "sans-serif"],
        mono: ["'JetBrains Mono'", "ui-monospace", "monospace"],
      },
      boxShadow: {
        soft: "0 1px 2px rgba(20,20,40,0.04), 0 8px 24px -12px rgba(20,20,60,0.12)",
        lift: "0 2px 6px rgba(20,20,40,0.06), 0 18px 40px -16px rgba(60,40,160,0.22)",
        glow: "0 0 0 4px rgba(91,91,240,0.12)",
      },
      keyframes: {
        rise: { "0%": { opacity: "0", transform: "translateY(8px)" }, "100%": { opacity: "1", transform: "translateY(0)" } },
        pop: { "0%": { opacity: "0", transform: "scale(0.96)" }, "100%": { opacity: "1", transform: "scale(1)" } },
        shimmer: { "0%": { backgroundPosition: "-200% 0" }, "100%": { backgroundPosition: "200% 0" } },
        orbit: { "0%": { transform: "rotate(0deg)" }, "100%": { transform: "rotate(360deg)" } },
        breathe: { "0%,100%": { transform: "scale(1)", opacity: "0.8" }, "50%": { transform: "scale(1.08)", opacity: "1" } },
      },
      animation: {
        rise: "rise .45s cubic-bezier(.2,.7,.2,1) both",
        pop: "pop .3s ease both",
        shimmer: "shimmer 1.6s linear infinite",
        orbit: "orbit 3s linear infinite",
        breathe: "breathe 2.4s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};
