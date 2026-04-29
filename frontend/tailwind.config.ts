import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./lib/**/*.{js,ts,jsx,tsx,mdx}"
  ],
  theme: {
    extend: {
      colors: {
        paper: {
          bg: "#f7f5ef",
          ink: "#1e2528",
          muted: "#66707a",
          line: "#d8d3c7",
          teal: "#0f766e",
          sky: "#2563eb",
          coral: "#b4533c"
        }
      },
      boxShadow: {
        soft: "0 18px 60px rgba(30, 37, 40, 0.10)"
      }
    }
  },
  plugins: []
};

export default config;

