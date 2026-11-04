/* ==========================================
   ECOTRACK - PROFESSIONAL CHARTS
   Chart.js
========================================== */

const ecoColors = {
  forest: "#153D2B",
  emerald: "#23845A",
  sage: "#91B99A",
  lightSage: "#DDEBDD",
  gold: "#B99A55",
  blue: "#668FA0",
  background: "#F5F7F2",
  muted: "#89958C",
  border: "#E4EAE2",
};

// Global Chart.js styling
if (typeof Chart !== "undefined") {
  Chart.defaults.font.family = "'DM Sans', sans-serif";
  Chart.defaults.font.size = 12;
  Chart.defaults.color = ecoColors.muted;
  Chart.defaults.plugins.legend.labels.usePointStyle = true;
  Chart.defaults.plugins.legend.labels.padding = 20;
  Chart.defaults.plugins.tooltip.backgroundColor = ecoColors.forest;
  Chart.defaults.plugins.tooltip.titleColor = "#FFFFFF";
  Chart.defaults.plugins.tooltip.bodyColor = "#FFFFFF";
  Chart.defaults.plugins.tooltip.padding = 12;
  Chart.defaults.plugins.tooltip.cornerRadius = 8;
}

let activityChart = null;
let carbonChart = null;
let restorationChart = null;

// Common chart options
function commonOptions() {
  return {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: "bottom",
      },
      tooltip: {
        enabled: true,
      },
    },
  };
}

// Create Sustainability Activity Doughnut Chart
function createActivityChart(canvasId, labels, values) {
  const canvas = document.getElementById(canvasId);

  if (!canvas || typeof Chart === "undefined") return;

  if (activityChart) activityChart.destroy();

  activityChart = new Chart(canvas, {
    type: "doughnut",
    data: {
      labels: labels,
      datasets: [
        {
          data: values,
          backgroundColor: [
            ecoColors.forest,
            ecoColors.emerald,
            ecoColors.sage,
            ecoColors.gold,
            ecoColors.blue,
          ],
          borderWidth: 3,
          borderColor: "#FFFFFF",
          hoverOffset: 8,
        },
      ],
    },
    options: {
      ...commonOptions(),
      cutout: "70%",
      plugins: {
        ...commonOptions().plugins,
        legend: {
          position: "bottom",
        },
      },
    },
  });
}

// Create Carbon Management Bar Chart
function createCarbonChart(canvasId, emissions, reductions, sequestration) {
  const canvas = document.getElementById(canvasId);

  if (!canvas || typeof Chart === "undefined") return;

  if (carbonChart) carbonChart.destroy();

  carbonChart = new Chart(canvas, {
    type: "bar",
    data: {
      labels: ["Emissions", "Reductions", "Sequestration"],
      datasets: [
        {
          label: "Carbon (tCO2e)",
          data: [emissions, reductions, sequestration],
          backgroundColor: [
            ecoColors.forest,
            ecoColors.emerald,
            ecoColors.sage,
          ],
          borderRadius: 7,
          maxBarThickness: 55,
        },
      ],
    },
    options: {
      ...commonOptions(),
      plugins: {
        ...commonOptions().plugins,
        legend: {
          display: false,
        },
      },
      scales: {
        y: {
          beginAtZero: true,
          grid: {
            color: ecoColors.border,
          },
          border: {
            display: false,
          },
        },
        x: {
          grid: {
            display: false,
          },
          border: {
            display: false,
          },
        },
      },
    },
  });
}

// Create Restoration Progress Chart
function createRestorationChart(
  canvasId,
  labels,
  targetValues,
  achievedValues,
) {
  const canvas = document.getElementById(canvasId);

  if (!canvas || typeof Chart === "undefined") return;

  if (restorationChart) restorationChart.destroy();

  restorationChart = new Chart(canvas, {
    type: "bar",
    data: {
      labels: labels,
      datasets: [
        {
          label: "Target Area",
          data: targetValues,
          backgroundColor: ecoColors.lightSage,
          borderRadius: 6,
        },
        {
          label: "Restored Area",
          data: achievedValues,
          backgroundColor: ecoColors.emerald,
          borderRadius: 6,
        },
      ],
    },
    options: {
      ...commonOptions(),
      scales: {
        y: {
          beginAtZero: true,
          grid: {
            color: ecoColors.border,
          },
          border: {
            display: false,
          },
        },
        x: {
          grid: {
            display: false,
          },
          border: {
            display: false,
          },
        },
      },
    },
  });
}

// Update dashboard charts using report API
async function loadEcoTrackCharts() {
  try {
    const response = await fetch("/api/reports/");

    if (!response.ok) {
      throw new Error("Unable to load report data.");
    }

    const data = await response.json();

    // Sustainability activity chart
    if (document.getElementById("activityChart")) {
      const summary = data.activity_summary || [];

      createActivityChart(
        "activityChart",
        summary.map((item) => item.activity_type),
        summary.map((item) => Number(item.total_achieved)),
      );
    }

    // Carbon chart
    if (document.getElementById("carbonChart")) {
      createCarbonChart(
        "carbonChart",
        Number(data.total_emissions || 0),
        Number(data.total_reductions || 0),
        Number(data.total_sequestration || 0),
      );
    }
  } catch (error) {
    console.error("EcoTrack chart error:", error);
  }
}

// Load charts after page loads
document.addEventListener("DOMContentLoaded", () => {
  if (typeof Chart === "undefined") {
    console.error("Chart.js is not loaded. Check the Chart.js CDN script.");
    return;
  }

  loadEcoTrackCharts();
});
