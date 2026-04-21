async function getJson(path) {
  const resp = await fetch(path);
  const data = await resp.json();
  if (!resp.ok) {
    throw new Error(JSON.stringify(data));
  }
  return data;
}

function print(id, obj) {
  const el = document.getElementById(id);
  el.textContent = JSON.stringify(obj, null, 2);
}

function asNumber(value) {
  const n = Number(value);
  return Number.isFinite(n) ? n : 0;
}

function fixed(value, digits = 2) {
  return asNumber(value).toFixed(digits);
}

function latest(rows) {
  if (!rows || rows.length === 0) return null;
  return rows[rows.length - 1];
}

let throughputChart;
let latencyChart;
let compressionChart;

function baseChartOptions() {
  return {
    responsive: true,
    maintainAspectRatio: false,
    animation: false,
    plugins: {
      legend: { labels: { color: "#2f4f6d" } },
      tooltip: {
        backgroundColor: "#ffffff",
        titleColor: "#1f3347",
        bodyColor: "#1f3347",
        borderColor: "#9fc0dd",
        borderWidth: 1,
      },
    },
    scales: {
      x: {
        ticks: { color: "#4f6780", maxRotation: 0, autoSkip: true, maxTicksLimit: 8 },
        grid: { color: "#e2ebf4" },
      },
      y: {
        ticks: { color: "#4f6780" },
        grid: { color: "#e2ebf4" },
      },
    },
  };
}

function createCharts() {
  const dpr = Math.max(1.5, window.devicePixelRatio || 1);
  const common = baseChartOptions();
  throughputChart = new Chart(document.getElementById("throughputChart"), {
    type: "line",
    data: { labels: [], datasets: [{ label: "events/min", data: [], borderColor: "#0067a5", backgroundColor: "rgba(0,103,165,0.16)", tension: 0.25, fill: true, pointRadius: 0 }] },
    options: { ...common, devicePixelRatio: dpr },
  });

  latencyChart = new Chart(document.getElementById("latencyChart"), {
    type: "line",
    data: {
      labels: [],
      datasets: [
        { label: "avg ms", data: [], borderColor: "#22c55e", backgroundColor: "rgba(34,197,94,0.16)", tension: 0.25, fill: true, pointRadius: 0 },
        { label: "p95 ms", data: [], borderColor: "#f59e0b", tension: 0.25, fill: false, pointRadius: 0 },
        { label: "p99 ms", data: [], borderColor: "#ef4444", tension: 0.25, fill: false, pointRadius: 0 },
      ],
    },
    options: { ...common, devicePixelRatio: dpr },
  });

  compressionChart = new Chart(document.getElementById("compressionChart"), {
    type: "line",
    data: {
      labels: [],
      datasets: [
        { label: "avg compression ratio", data: [], borderColor: "#a78bfa", backgroundColor: "rgba(167,139,250,0.18)", tension: 0.25, fill: true, pointRadius: 0 },
        { label: "pct SDT flagged", data: [], borderColor: "#0082cf", tension: 0.25, fill: false, pointRadius: 0 },
      ],
    },
    options: { ...common, devicePixelRatio: dpr },
  });
}

function updateKpis(health, throughputRows, latencyRows, compressionRows) {
  const healthEl = document.getElementById("kpiHealth");
  const healthDetailEl = document.getElementById("kpiHealthDetail");
  healthEl.textContent = health?.status || "unknown";
  healthEl.style.color = health?.status === "ok" ? "#22c55e" : "#ef4444";
  healthDetailEl.textContent = health?.configured ? "configured" : (health?.error || "not configured");

  const t = latest(throughputRows);
  const l = latest(latencyRows);
  const c = latest(compressionRows);

  document.getElementById("kpiEventsPerMin").textContent = t ? String(asNumber(t.events).toLocaleString()) : "-";
  document.getElementById("kpiP99Latency").textContent = l ? fixed(l.p99_latency_ms, 0) : "-";
  document.getElementById("kpiCompressionRatio").textContent = c ? fixed(c.avg_compression_ratio, 3) : "-";
}

function updateTable(rows) {
  const head = document.getElementById("latestHead");
  const body = document.getElementById("latestBody");
  head.innerHTML = "";
  body.innerHTML = "";
  if (!rows || rows.length === 0) return;
  const cols = Object.keys(rows[0]);
  cols.forEach((c) => {
    const th = document.createElement("th");
    th.textContent = c;
    head.appendChild(th);
  });
  rows.slice(-8).reverse().forEach((r) => {
    const tr = document.createElement("tr");
    cols.forEach((c) => {
      const td = document.createElement("td");
      td.textContent = String(r[c] ?? "");
      tr.appendChild(td);
    });
    body.appendChild(tr);
  });
}

function updateCharts(throughputRows, latencyRows, compressionRows) {
  const tLabels = throughputRows.map((r) => r.minute_bucket);
  throughputChart.data.labels = tLabels;
  throughputChart.data.datasets[0].data = throughputRows.map((r) => asNumber(r.events));
  throughputChart.update();

  const lLabels = latencyRows.map((r) => r.minute_bucket);
  latencyChart.data.labels = lLabels;
  latencyChart.data.datasets[0].data = latencyRows.map((r) => asNumber(r.avg_latency_ms));
  latencyChart.data.datasets[1].data = latencyRows.map((r) => asNumber(r.p95_latency_ms));
  latencyChart.data.datasets[2].data = latencyRows.map((r) => asNumber(r.p99_latency_ms));
  latencyChart.update();

  const cLabels = compressionRows.map((r) => r.minute_bucket);
  compressionChart.data.labels = cLabels;
  compressionChart.data.datasets[0].data = compressionRows.map((r) => asNumber(r.avg_compression_ratio));
  compressionChart.data.datasets[1].data = compressionRows.map((r) => asNumber(r.pct_sdt_flagged));
  compressionChart.update();
}

async function refresh() {
  const minutes = Number(document.getElementById("minutes").value || 15);
  try {
    const health = await getJson("/api/health");
    print("health", health);

    const [throughput, latency, compression] = await Promise.all([
      getJson(`/api/metrics/throughput?minutes=${minutes}`),
      getJson(`/api/metrics/latency?minutes=${minutes}`),
      getJson(`/api/metrics/compression?minutes=${minutes}`),
    ]);

    print("throughput", throughput);
    print("latency", latency);
    print("compression", compression);

    const throughputRows = throughput?.data || [];
    const latencyRows = latency?.data || [];
    const compressionRows = compression?.data || [];
    updateKpis(health, throughputRows, latencyRows, compressionRows);
    updateCharts(throughputRows, latencyRows, compressionRows);
    updateTable(latencyRows);
  } catch (err) {
    print("health", { error: String(err) });
    document.getElementById("kpiHealth").textContent = "error";
    document.getElementById("kpiHealth").style.color = "#ef4444";
    document.getElementById("kpiHealthDetail").textContent = String(err);
  }
}

document.getElementById("refresh").addEventListener("click", refresh);
createCharts();
refresh();

