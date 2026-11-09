/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./app/templates/**/*.html",
    "./app/static/js/**/*.js",
  ],
  // Classes generated dynamically via Jinja (e.g. badge-{{ status }})
  // are not detected by the content scanner, so they must be safelisted.
  safelist: [
    // Flash-message alert variants: alert-{{ category }}
    "alert-success",
    "alert-danger",
    "alert-warning",
    "alert-info",
    // Badge status variants: badge-{{ obj.status }}
    {
      pattern:
        /^badge-(success|active|completed|warning|planned|danger|cancelled|flagged|info|in_progress|duplicate|inactive|pending|missed)$/,
    },
    // Badge role variants: badge-{{ user.role }}
    {
      pattern:
        /^badge-role-(admin|field_officer|warehouse|logistics|programme_coord|partner)$/,
    },
    // Badge category variants: badge-{{ item.category }}
    {
      pattern:
        /^badge-category-(food|water|medicine|shelter|clothing|hygiene|other)$/,
    },
    // Stat-card colour variants
    "stat-blue",
    "stat-green",
    "stat-orange",
    "stat-red",
    "stat-teal",
    // Stock-bar colour variants
    "stock-low",
    "stock-medium",
    "stock-ok",
    // Bar-fill colour variants
    "bar-fill-blue",
    "bar-fill-orange",
    // Vuln-tag active state
    "active",
  ],
  theme: {
    extend: {
      colors: {
        // Brand palette
        primary: {
          DEFAULT: "#7FDA89", // primary green
          dark: "#259073", // dark green (text / hover)
          light: "#E6F99D", // accent lime
        },
        // Semantic colours kept in a dedicated namespace for badges/alerts
        nrds: {
          success: "#057a55",
          "success-bg": "#def7ec",
          warning: "#92400e",
          "warning-bg": "#fef3c7",
          danger: "#9b1c1c",
          "danger-bg": "#fde8e8",
          info: "#1e3a5f",
          "info-bg": "#e1effe",
        },
      },
      fontFamily: {
        sans: [
          "-apple-system",
          "BlinkMacSystemFont",
          '"Segoe UI"',
          "Roboto",
          "sans-serif",
        ],
      },
      boxShadow: {
        card: "0 1px 3px rgba(0,0,0,.4), 0 1px 2px rgba(0,0,0,.3)",
        "card-md": "0 4px 6px rgba(0,0,0,.4), 0 2px 4px rgba(0,0,0,.3)",
      },
    },
  },
  plugins: [],
};
