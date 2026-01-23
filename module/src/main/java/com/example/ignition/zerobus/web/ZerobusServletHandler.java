package com.example.ignition.zerobus.web;

import com.example.ignition.zerobus.ConfigModel;
import com.example.ignition.zerobus.ZerobusRuntime;
import com.google.gson.Gson;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.InputStream;
import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.stream.Collectors;

/**
 * Shared HTTP handler logic for both servlet namespaces:
 * - Ignition 8.1/8.2: javax.servlet.*
 * - Ignition 8.3+:    jakarta.servlet.*
 *
 * This avoids duplicating endpoint logic and keeps the "javax vs jakarta" split to the servlet wrappers only.
 */
public final class ZerobusServletHandler {
    private static final Logger logger = LoggerFactory.getLogger(ZerobusServletHandler.class);
    private static final Gson gson = new Gson();

    private ZerobusServletHandler() {
        // no-op
    }

    public static Response handle(String method, String pathInfo, String body) {
        String path = normalizePath(pathInfo);

        ZerobusConfigResource resource = ZerobusConfigResourceHolder.get();
        ZerobusRuntime runtime = (resource != null) ? resource.getRuntime() : null;

        try {
            if ("GET".equalsIgnoreCase(method)) {
                return handleGet(runtime, path);
            }
            if ("POST".equalsIgnoreCase(method)) {
                return handlePost(runtime, path, body == null ? "" : body);
            }
            return Response.json(405, "{\"error\":\"method_not_allowed\"}");
        } catch (Throwable t) {
            logger.error("Unhandled error handling {} {}", method, path, t);
            return Response.json(500, "{\"error\":\"internal_error\"}");
        }
    }

    private static Response handleGet(ZerobusRuntime runtime, String path) {
        // Serve HTML configuration page
        if ("/configure".equals(path)) {
            return serveConfigPage();
        }

        if ("/".equals(path) || "/health".equals(path)) {
            boolean enabled = runtime != null && runtime.getConfigModel() != null && runtime.getConfigModel().isEnabled();
            return Response.json(200, "{\"status\":\"ok\",\"enabled\":" + enabled + "}");
        }

        if ("/diagnostics".equals(path)) {
            if (runtime == null) {
                return Response.text(500, "Zerobus diagnostics unavailable (hook not initialized)");
            }
            return Response.text(200, runtime.getDiagnosticsInfo());
        }

        if ("/config".equals(path)) {
            if (runtime == null) {
                return Response.json(500, "{\"error\":\"hook_not_initialized\"}");
            }
            ConfigModel cfg = runtime.getConfigModel();
            if (cfg == null) {
                return Response.json(500, "{\"error\":\"config_not_initialized\"}");
            }

            // Redact secret on read
            JsonElement tree = gson.toJsonTree(cfg);
            if (tree != null && tree.isJsonObject()) {
                JsonObject obj = tree.getAsJsonObject();
                if (obj.has("oauthClientSecret")) {
                    String secret = cfg.getOauthClientSecret();
                    obj.addProperty("oauthClientSecret", (secret == null || secret.isEmpty()) ? "" : "****");
                }
                return Response.json(200, gson.toJson(obj));
            }

            return Response.json(200, gson.toJson(cfg));
        }

        return Response.json(404, "{\"error\":\"not_found\"}");
    }

    private static Response handlePost(ZerobusRuntime runtime, String path, String body) {
        if (runtime == null) {
            return Response.json(500, "{\"error\":\"hook_not_initialized\"}");
        }

        if ("/config".equals(path)) {
            ConfigModel newCfg;
            try {
                newCfg = gson.fromJson(body, ConfigModel.class);
            } catch (Exception e) {
                return Response.json(400, "{\"error\":\"invalid_json\"}");
            }

            if (newCfg == null) {
                return Response.json(400, "{\"error\":\"invalid_config\"}");
            }

            // Preserve secret if UI sends blank/"****" (masked). This allows updating other fields without
            // overwriting the stored secret.
            String incomingSecret = newCfg.getOauthClientSecret();
            if (incomingSecret == null || incomingSecret.isBlank() || "****".equals(incomingSecret)) {
                ConfigModel existing = runtime.getConfigModel();
                String existingSecret = existing == null ? null : existing.getOauthClientSecret();
                if (existingSecret != null && !existingSecret.isBlank()) {
                    newCfg.setOauthClientSecret(existingSecret);
                }
            }

            // Normalize any paths coming from UI/restores so the connector doesn't wedge on startup.
            newCfg.autoCorrectPaths();

            List<String> errors = newCfg.validate();
            if (errors != null && !errors.isEmpty()) {
                JsonObject resp = new JsonObject();
                resp.addProperty("success", false);
                resp.addProperty("error", "validation_failed");
                resp.add("details", gson.toJsonTree(errors));
                return Response.json(400, gson.toJson(resp));
            }

            try {
                runtime.saveConfiguration(newCfg);
            } catch (Exception e) {
                JsonObject resp = new JsonObject();
                resp.addProperty("success", false);
                resp.addProperty("error", "save_failed");
                resp.addProperty("message", e.getMessage() == null ? "save_failed" : e.getMessage());
                return Response.json(500, gson.toJson(resp));
            }

            JsonObject resp = new JsonObject();
            resp.addProperty("success", true);
            return Response.json(200, gson.toJson(resp));
        }

        if ("/test-connection".equals(path)) {
            boolean ok = runtime.testConnection();
            JsonObject resp = new JsonObject();
            resp.addProperty("success", ok);
            resp.addProperty("message", ok ? "Connection test successful" : "Connection test failed");
            return Response.json(ok ? 200 : 400, gson.toJson(resp));
        }

        if ("/restart-services".equals(path)) {
            boolean ok = runtime.restartServices();
            JsonObject resp = new JsonObject();
            resp.addProperty("success", ok);
            resp.addProperty("message", ok ? "Services restarted" : "Services restart failed");
            return Response.json(ok ? 200 : 500, gson.toJson(resp));
        }

        if ("/ingest".equals(path)) {
            TagEventPayload payload;
            try {
                payload = gson.fromJson(body, TagEventPayload.class);
            } catch (Exception e) {
                return Response.json(400, "{\"error\":\"invalid_json\"}");
            }
            if (payload == null) {
                return Response.json(400, "{\"error\":\"invalid_payload\"}");
            }
            boolean accepted = runtime.ingestTagEvent(payload);
            JsonObject resp = new JsonObject();
            resp.addProperty("received", 1);
            resp.addProperty("accepted", accepted ? 1 : 0);
            resp.addProperty("dropped", accepted ? 0 : 1);
            return Response.json(200, gson.toJson(resp));
        }

        if ("/ingest/batch".equals(path)) {
            TagEventPayload[] payloads;
            try {
                payloads = gson.fromJson(body, TagEventPayload[].class);
            } catch (Exception e) {
                return Response.json(400, "{\"error\":\"invalid_json\"}");
            }

            int received = payloads == null ? 0 : payloads.length;
            int accepted = received == 0 ? 0 : runtime.ingestTagEventBatch(payloads);
            int dropped = Math.max(0, received - accepted);

            JsonObject resp = new JsonObject();
            resp.addProperty("received", received);
            resp.addProperty("accepted", accepted);
            resp.addProperty("dropped", dropped);
            return Response.json(200, gson.toJson(resp));
        }

        return Response.json(404, "{\"error\":\"not_found\"}");
    }

    private static String normalizePath(String pathInfo) {
        if (pathInfo == null) {
            return "/";
        }
        String p = pathInfo.trim();
        return p.isEmpty() ? "/" : p;
    }

    /**
     * Serve the HTML configuration page from resources
     */
    private static Response serveConfigPage() {
        try {
            InputStream is = ZerobusServletHandler.class.getResourceAsStream("/web/zerobus-config.html");
            if (is == null) {
                logger.error("Configuration page resource not found: /web/zerobus-config.html");
                return Response.html(404, "<html><body><h1>404 - Configuration page not found</h1></body></html>");
            }

            String html = new BufferedReader(new InputStreamReader(is, StandardCharsets.UTF_8))
                    .lines()
                    .collect(Collectors.joining("\n"));

            return Response.html(200, html);
        } catch (Exception e) {
            logger.error("Failed to load configuration page", e);
            return Response.html(500, "<html><body><h1>500 - Failed to load configuration page</h1></body></html>");
        }
    }

    public static final class Response {
        public final int status;
        public final String contentType;
        public final String body;

        private Response(int status, String contentType, String body) {
            this.status = status;
            this.contentType = contentType;
            this.body = body;
        }

        public static Response json(int status, String body) {
            return new Response(status, "application/json", body);
        }

        public static Response text(int status, String body) {
            return new Response(status, "text/plain", body);
        }

        public static Response html(int status, String body) {
            return new Response(status, "text/html; charset=UTF-8", body);
        }
    }
}


