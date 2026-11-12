/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // SAP Fiori 3 palette
        shell: "#354a5f",
        shell2: "#2b3c4e",
        bg: "#f5f6f7",
        tile: "#ffffff",
        line: "#e5e5e5",
        line2: "#d9d9d9",
        ink: "#32363a",
        sub: "#6a6d70",
        brand: "#0a6ed1",
        brand2: "#0854a0",
        good: "#107e3e",
        warn: "#e9730c",
        bad: "#bb0000",
        crit: "#6c2d91",
        info: "#0a6ed1",
      },
      fontFamily: { sans: ["'72'", "Inter", "Arial", "system-ui", "sans-serif"] },
      boxShadow: {
        tile: "0 0 0 1px rgba(0,0,0,0.04), 0 1px 4px rgba(0,0,0,0.08)",
        pop: "0 2px 10px rgba(0,0,0,0.15)",
      },
    },
  },
  plugins: [],
};
