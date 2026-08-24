import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class"],
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Design token mappings — change globals.css variables to re-skin
        background:     "hsl(var(--background))",
        foreground:     "hsl(var(--foreground))",
        surface:        "hsl(var(--surface))",
        "surface-elevated": "hsl(var(--surface-elevated))",
        "surface-dark": "hsl(var(--surface-dark))",
        border:         "hsl(var(--border))",
        "border-strong":"hsl(var(--border-strong))",
        input:          "hsl(var(--input))",
        ring:           "hsl(var(--ring))",
        card: {
          DEFAULT:     "hsl(var(--card))",
          foreground:  "hsl(var(--card-foreground))",
        },
        primary: {
          DEFAULT:     "hsl(var(--primary))",
          foreground:  "hsl(var(--text-on-brand))",
          soft:        "hsl(var(--brand-primary-soft))",
        },
        secondary: {
          DEFAULT:     "hsl(var(--secondary))",
          foreground:  "hsl(var(--secondary-foreground))",
        },
        muted: {
          DEFAULT:     "hsl(var(--muted))",
          foreground:  "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT:     "hsl(var(--accent))",
          foreground:  "hsl(var(--accent-foreground))",
        },
        destructive: {
          DEFAULT:     "hsl(var(--destructive))",
          foreground:  "hsl(var(--destructive-foreground))",
        },
        success: {
          DEFAULT:     "hsl(var(--success))",
          soft:        "hsl(var(--success-soft))",
        },
        warning: {
          DEFAULT:     "hsl(var(--warning))",
          soft:        "hsl(var(--warning-soft))",
        },
        danger: {
          DEFAULT:     "hsl(var(--danger))",
          soft:        "hsl(var(--danger-soft))",
        },
        // Brand
        brand: {
          primary: "hsl(var(--brand-primary))",
          hover:   "hsl(var(--brand-primary-hover))",
          soft:    "hsl(var(--brand-primary-soft))",
        },
        // Text semantic
        "text-primary":   "hsl(var(--text-primary))",
        "text-secondary": "hsl(var(--text-secondary))",
        "text-tertiary":  "hsl(var(--text-tertiary))",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "Fira Code", "monospace"],
      },
      borderRadius: {
        lg:  "var(--radius)",
        md:  "calc(var(--radius) - 2px)",
        sm:  "calc(var(--radius) - 4px)",
        xl:  "calc(var(--radius) + 4px)",
        "2xl": "calc(var(--radius) + 8px)",
      },
      boxShadow: {
        card:    "0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04)",
        "card-hover": "0 4px 12px rgba(0,0,0,0.08), 0 2px 4px rgba(0,0,0,0.04)",
        panel:   "0 8px 32px rgba(0,0,0,0.08)",
        glass:   "0 8px 32px rgba(0,0,0,0.10)",
      },
      animation: {
        "pulse-ring": "pulse-ring 1.5s ease-out infinite",
        "fade-in":    "fade-in 0.2s ease-out",
        "slide-up":   "slide-up 0.3s ease-out",
      },
      keyframes: {
        "fade-in":  { from: { opacity: "0" }, to: { opacity: "1" } },
        "slide-up": { from: { transform: "translateY(8px)", opacity: "0" }, to: { transform: "translateY(0)", opacity: "1" } },
      },
    },
  },
  plugins: [],
};

export default config;
