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
  } catch (err) {
    print("health", { error: String(err) });
  }
}

document.getElementById("refresh").addEventListener("click", refresh);
refresh();

