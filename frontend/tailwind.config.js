/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ulpin: {
          navy: "#0b2545",
          blue: "#13315c",
          teal: "#16a085",
          amber: "#f39c12",
        },
      },
    },
  },
  plugins: [],
};
