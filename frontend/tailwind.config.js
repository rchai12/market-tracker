/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        bullish: "#22c55e",
        bearish: "#ef4444",
        neutral: "#6b7280",
      },
    },
  },
  plugins: [],
};
