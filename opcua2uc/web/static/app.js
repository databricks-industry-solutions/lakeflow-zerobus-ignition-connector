/* global React, ReactDOM */

function useInterval(callback, delayMs) {
  const savedRef = React.useRef(callback);
  React.useEffect(() => {
    savedRef.current = callback;
  }, [callback]);

  React.useEffect(() => {
    if (delayMs == null) return;
    const id = setInterval(() => savedRef.current(), delayMs);
    return () => clearInterval(id);
  }, [delayMs]);
}

async function apiGet(path) {
  const r = await fetch(path, { headers: { Accept: "application/json" } });
  const body = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(body.error || `HTTP ${r.status}`);
  return body;
}

async function apiPost(path, payload) {
  const r = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify(payload),
  });
  const body = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(body.error || `HTTP ${r.status}`);
  return body;
}

async function apiDelete(path) {
  const r = await fetch(path, { method: "DELETE", headers: { Accept: "application/json" } });
  const body = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(body.error || `HTTP ${r.status}`);
  return body;
}

function Card(props) {
  return React.createElement("div", { className: "card" }, props.children);
}

function App() {
  const [status, setStatus] = React.useState(null);
  const [cfg, setCfg] = React.useState(null);
  const [cfgText, setCfgText] = React.useState("");
  const [sources, setSources] = React.useState([]);
  const [newSourceName, setNewSourceName] = React.useState("");
  const [newSourceEndpoint, setNewSourceEndpoint] = React.useState("");
  const [testingName, setTestingName] = React.useState(null);
  const [error, setError] = React.useState(null);
  const [saving, setSaving] = React.useState(false);

  const refresh = React.useCallback(async () => {
    try {
      setError(null);
      const [s, c, src] = await Promise.all([
        apiGet("/api/status"),
        apiGet("/api/config"),
        apiGet("/api/sources"),
      ]);
      setStatus(s);
      setCfg(c);
      setCfgText(JSON.stringify(c, null, 2));
      setSources(Array.isArray(src) ? src : []);
    } catch (e) {
      setError(String(e && e.message ? e.message : e));
    }
  }, []);

  React.useEffect(() => {
    refresh();
  }, [refresh]);

  useInterval(() => {
    apiGet("/api/status")
      .then(setStatus)
      .catch((e) => setError(String(e && e.message ? e.message : e)));
  }, 2000);

  async function onSave() {
    try {
      setSaving(true);
      setError(null);
      const next = JSON.parse(cfgText);
      await apiPost("/api/config", next);
      await refresh();
    } catch (e) {
      setError(String(e && e.message ? e.message : e));
    } finally {
      setSaving(false);
    }
  }

  async function onAddSource() {
    try {
      setError(null);
      const name = newSourceName.trim();
      const endpoint = newSourceEndpoint.trim();
      await apiPost("/api/sources", { name, endpoint });
      setNewSourceName("");
      setNewSourceEndpoint("");
      await refresh();
    } catch (e) {
      setError(String(e && e.message ? e.message : e));
    }
  }

  async function onDeleteSource(name) {
    try {
      setError(null);
      await apiDelete(`/api/sources/${encodeURIComponent(name)}`);
      await refresh();
    } catch (e) {
      setError(String(e && e.message ? e.message : e));
    }
  }

  async function onTestSource(name) {
    try {
      setTestingName(name);
      setError(null);
      const res = await apiPost(`/api/sources/${encodeURIComponent(name)}/test`, {});
      alert(res.ok ? `OK: ${name}\n${res.note || ""}` : `FAILED: ${name}`);
    } catch (e) {
      setError(String(e && e.message ? e.message : e));
    } finally {
      setTestingName(null);
    }
  }

  return React.createElement(
    "div",
    { className: "container" },
    React.createElement("div", { className: "header" }, "OPC UA Connector (Edge)"),
    error ? React.createElement("div", { className: "error" }, error) : null,
    React.createElement(
      "div",
      { className: "grid" },
      React.createElement(
        Card,
        null,
        React.createElement("div", { className: "cardTitle" }, "Status"),
        status
          ? React.createElement("pre", { className: "pre" }, JSON.stringify(status, null, 2))
          : React.createElement("div", { className: "muted" }, "Loading…")
      ),
      React.createElement(
        Card,
        null,
        React.createElement("div", { className: "cardTitle" }, "Sources"),
        React.createElement(
          "div",
          { className: "stack" },
          React.createElement(
            "div",
            { className: "row" },
            React.createElement("input", {
              className: "input",
              placeholder: "name (e.g. honeywell-phd)",
              value: newSourceName,
              onChange: (e) => setNewSourceName(e.target.value),
            }),
            React.createElement("input", {
              className: "input",
              placeholder: "endpoint (e.g. opc.tcp://phd-server:4840)",
              value: newSourceEndpoint,
              onChange: (e) => setNewSourceEndpoint(e.target.value),
            }),
            React.createElement(
              "button",
              { className: "button", onClick: onAddSource, disabled: !newSourceName.trim() || !newSourceEndpoint.trim() },
              "Add"
            )
          ),
          sources && sources.length
            ? React.createElement(
                "div",
                { className: "list" },
                sources.map((s) =>
                  React.createElement(
                    "div",
                    { key: s.name || s.endpoint, className: "listRow" },
                    React.createElement("div", { className: "listMain" }, [
                      React.createElement("div", { key: "n", className: "listName" }, s.name || "(no name)"),
                      React.createElement(
                        "div",
                        { key: "e", className: "listMeta" },
                        s.endpoint || ""
                      ),
                    ]),
                    React.createElement(
                      "div",
                      { className: "listActions" },
                      React.createElement(
                        "button",
                        {
                          className: "button buttonSmall",
                          onClick: () => onTestSource(s.name),
                          disabled: !s.name || testingName === s.name,
                        },
                        testingName === s.name ? "Testing…" : "Test"
                      ),
                      React.createElement(
                        "button",
                        { className: "button buttonSmall danger", onClick: () => onDeleteSource(s.name), disabled: !s.name },
                        "Remove"
                      )
                    )
                  )
                )
              )
            : React.createElement("div", { className: "muted" }, "No sources configured yet.")
        )
      ),
      React.createElement(
        Card,
        null,
        React.createElement("div", { className: "cardTitle" }, "Config (advanced)"),
        cfg
          ? React.createElement(
              React.Fragment,
              null,
              React.createElement("textarea", {
                className: "textarea",
                value: cfgText,
                onChange: (e) => setCfgText(e.target.value),
                spellCheck: false,
              }),
              React.createElement(
                "div",
                { className: "row" },
                React.createElement(
                  "button",
                  { className: "button", onClick: onSave, disabled: saving },
                  saving ? "Saving…" : "Save"
                ),
                React.createElement(
                  "a",
                  {
                    className: "link",
                    href: `http://${location.hostname}:9090/metrics`,
                    target: "_blank",
                    rel: "noreferrer",
                  },
                  "Metrics"
                )
              )
            )
          : React.createElement("div", { className: "muted" }, "Loading…")
      )
    )
  );
}

ReactDOM.render(React.createElement(App), document.getElementById("root"));


