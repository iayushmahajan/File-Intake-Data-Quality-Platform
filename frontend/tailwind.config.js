const color = (name) => `rgb(var(--${name}) / <alpha-value>)`;

export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: { extend: {
    colors: {
      background: color("background"), foreground: color("foreground"),
      surface: color("surface"), secondary: color("secondary"), border: color("border"),
      primary: { DEFAULT: color("primary"), foreground: color("primary-foreground") },
      brand: { DEFAULT: color("brand"), foreground: color("brand-foreground") },
      muted: { DEFAULT: color("secondary"), foreground: color("muted") },
      overlay: color("overlay"), success: color("success"), warning: color("warning"), danger: color("danger"),
      // Compatibility aliases keep existing feature components readable and functional.
      surfaceSoft: color("secondary"), borderSoft: color("border"), textMain: color("foreground"),
      textMuted: color("muted"), accent: color("primary"), accentSoft: color("link"),
      chartMint: color("chart-mint"), chartTeal: color("chart-teal"), chartPurple: color("chart-slate"),
    },
    boxShadow: { panel: "0 2px 8px rgb(20 40 35 / 0.05)", glow: "0 0 0 3px rgb(20 40 35 / 0.16)" },
  } },
  plugins: [],
};
