/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Clinia-inspired editorial palette: warm paper, charcoal ink, warm-tan accent.
        shell: "#1a1a1e",   // charcoal nav / dark panels
        shell2: "#101013",
        bg: "#f6f3ec",      // warm paper
        tile: "#ffffff",
        line: "#ece7dd",    // warm hairline
        line2: "#ddd6c9",
        ink: "#1a1a1e",
        sub: "#77726a",     // warm grey
        brand: "#1a1a1e",   // primary action = charcoal (Clinia "book a demo" button)
        brand2: "#000000",
        accent: "#95795c",  // warm tan — eyebrow labels, highlights
        accent2: "#b89b74",
        cream: "#fcf8ef",
        good: "#2f6b4f",
        warn: "#b5703a",
        bad: "#a23b2e",
        crit: "#6c4a8f",
        info: "#1a1a1e",
      },
      fontFamily: {
        sans: ["Manrope", "Inter", "system-ui", "sans-serif"],
        serif: ["Fraunces", "Georgia", "serif"],
        mono: ["'JetBrains Mono'", "ui-monospace", "monospace"],
      },
      boxShadow: {
        tile: "0 1px 2px rgba(26,26,30,0.04), 0 1px 3px rgba(26,26,30,0.06)",
        pop: "0 8px 30px rgba(26,26,30,0.16)",
      },
    },
  },
  plugins: [],
};
