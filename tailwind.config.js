/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./backend/templates/**/*.html",
    "./backend/static/**/*.js",
  ],
  theme: { extend: {} },
  plugins: [require("daisyui")],
  daisyui: { themes: ["light", "dark"] },
}

