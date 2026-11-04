document.addEventListener("DOMContentLoaded", function () {
  // EcoTrack module icons
  const moduleIcons = {
    Dashboard: "📊",
    Projects: "📁",
    Sustainability: "🌱",
    Restoration: "🌳",
    "Ecosystem Restoration": "🌳",
    Carbon: "☁️",
    "Carbon Management": "☁️",
    "Carbon Credits": "🪙",
    Biodiversity: "🦋",
    Reports: "📈",
    "Reports & Analytics": "📈",
    "Audit History": "📋",
    "User Management": "👥",
  };

  // Add emojis to navigation links
  document.querySelectorAll(".navigation a, .side-link").forEach((link) => {
    const label = link.textContent.trim();

    if (moduleIcons[label] && !link.dataset.iconAdded) {
      link.textContent = moduleIcons[label] + " " + label;
      link.dataset.iconAdded = "true";
    }
  });

  // Highlight the current navigation page
  const currentPath = window.location.pathname;

  document.querySelectorAll(".navigation a, .side-link").forEach((link) => {
    const linkPath = new URL(link.href, window.location.origin).pathname;

    if (linkPath === currentPath) {
      link.classList.add("active");
    }
  });
});
