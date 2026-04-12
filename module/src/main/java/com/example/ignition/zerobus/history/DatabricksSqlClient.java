package com.example.ignition.zerobus.history;

import com.example.ignition.zerobus.ConfigModel;
import com.google.gson.Gson;
import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.ArrayList;
import java.util.List;

/**
 * Client for the Databricks SQL Statement Execution REST API.
 *
 * <p>Full lifecycle:
 * <ol>
 *   <li>Submit: {@code POST {workspaceUrl}/api/2.0/sql/statements}</li>
 *   <li>Poll: {@code GET {workspaceUrl}/api/2.0/sql/statements/{id}}</li>
 *   <li>Paginate: {@code GET {workspaceUrl}/api/2.0/sql/statements/{id}/result/chunks/{idx}}</li>
 * </ol>
 *
 * <p>Auth: resolves a fresh Bearer token per query via {@link #resolveToken()} (no caching).
 * Uses {@code java.net.http.HttpClient} (JDK 11+) — no additional dependencies beyond Gson.
 *
 * <p><b>Important — column names:</b> All queries must use proto field names as Delta column names:
 * {@code tag_path} (STRING), {@code event_time} (BIGINT µs since epoch),
 * {@code numeric_value} (DOUBLE), {@code quality_code} (INT).
 * Do NOT use the demo {@code setup_tables.sql} column names (different schema).
 */
public class DatabricksSqlClient {

    private static final Logger logger = LoggerFactory.getLogger(DatabricksSqlClient.class);
    private static final Gson gson = new Gson();

    /** Poll interval when waiting for a statement to complete (ms). */
    private static final long POLL_INTERVAL_MS = 500L;

    /** Maximum rows returned per query (safety cap for NFR-2). */
    static final int MAX_ROWS = 10_000;

    private final ConfigModel config;
    private final HttpClient httpClient;

    public DatabricksSqlClient(ConfigModel config) {
        this.config = config;
        this.httpClient = HttpClient.newBuilder()
                .connectTimeout(Duration.ofMillis(config.getConnectionTimeoutMs()))
                .build();
    }

    /**
     * Executes a SQL statement synchronously, polling until SUCCEEDED or timeout.
     * Paginates through all result chunks (NFR-2: handles up to {@value #MAX_ROWS} rows).
     *
     * @param sql       SQL statement to execute
     * @param timeoutMs maximum wall-clock time to wait for completion
     * @return rows as {@code List<Object[]>} — each array element is a column value (String or null)
     * @throws Exception on HTTP error, SQL failure, or timeout
     */
    public List<Object[]> executeQuery(String sql, long timeoutMs) throws Exception {
        String token = resolveToken();
        String baseUrl = normalizeWorkspaceUrl(config.getWorkspaceUrl());
        String warehouseId = config.getWarehouseId();

        if (warehouseId == null || warehouseId.isEmpty()) {
            throw new IllegalStateException("warehouseId must be configured for history queries");
        }

        // --- Submit statement ---
        JsonObject submitBody = new JsonObject();
        submitBody.addProperty("statement", sql);
        submitBody.addProperty("warehouse_id", warehouseId);
        submitBody.addProperty("wait_timeout", "0s");
        submitBody.addProperty("on_wait_timeout", "CONTINUE");
        submitBody.addProperty("disposition", "INLINE");
        submitBody.addProperty("format", "JSON_ARRAY");

        HttpRequest submitReq = HttpRequest.newBuilder()
                .uri(URI.create(baseUrl + "/api/2.0/sql/statements"))
                .header("Authorization", "Bearer " + token)
                .header("Content-Type", "application/json")
                .POST(HttpRequest.BodyPublishers.ofString(submitBody.toString(), StandardCharsets.UTF_8))
                .timeout(Duration.ofMillis(config.getRequestTimeoutMs()))
                .build();

        HttpResponse<String> submitResp = httpClient.send(submitReq, HttpResponse.BodyHandlers.ofString());
        if (submitResp.statusCode() != 200) {
            throw new RuntimeException("SQL statement submit failed (HTTP "
                    + submitResp.statusCode() + "): " + submitResp.body());
        }

        JsonObject result = gson.fromJson(submitResp.body(), JsonObject.class);
        String statementId = result.get("statement_id").getAsString();
        String state = result.getAsJsonObject("status").get("state").getAsString();

        // --- Poll until SUCCEEDED, FAILED, CANCELED, or CLOSED ---
        long deadline = System.currentTimeMillis() + timeoutMs;
        while ("PENDING".equals(state) || "RUNNING".equals(state)) {
            if (System.currentTimeMillis() > deadline) {
                // Best-effort cancel before throwing
                cancelStatement(baseUrl, statementId, token);
                throw new RuntimeException("SQL statement timed out after " + timeoutMs
                        + "ms (statementId=" + statementId + ")");
            }
            Thread.sleep(POLL_INTERVAL_MS);

            HttpRequest pollReq = HttpRequest.newBuilder()
                    .uri(URI.create(baseUrl + "/api/2.0/sql/statements/" + statementId))
                    .header("Authorization", "Bearer " + token)
                    .GET()
                    .timeout(Duration.ofMillis(config.getRequestTimeoutMs()))
                    .build();

            HttpResponse<String> pollResp = httpClient.send(pollReq, HttpResponse.BodyHandlers.ofString());
            if (pollResp.statusCode() != 200) {
                throw new RuntimeException("SQL statement poll failed (HTTP " + pollResp.statusCode() + ")");
            }
            result = gson.fromJson(pollResp.body(), JsonObject.class);
            state = result.getAsJsonObject("status").get("state").getAsString();
        }

        if (!"SUCCEEDED".equals(state)) {
            String errMsg = "";
            JsonObject status = result.getAsJsonObject("status");
            if (status != null && status.has("error")) {
                JsonObject err = status.getAsJsonObject("error");
                if (err != null && err.has("message")) {
                    errMsg = err.get("message").getAsString();
                }
            }
            throw new RuntimeException("SQL statement failed (state=" + state
                    + ", statementId=" + statementId + "): " + errMsg);
        }

        // --- Collect all result rows, paginating through chunks ---
        List<Object[]> allRows = new ArrayList<>();
        extractRows(result, allRows);

        // Paginate: follow next_chunk_index links
        JsonObject resultObj = result.has("result") && !result.get("result").isJsonNull()
                ? result.getAsJsonObject("result") : null;

        while (resultObj != null
                && resultObj.has("next_chunk_index")
                && !resultObj.get("next_chunk_index").isJsonNull()
                && allRows.size() < MAX_ROWS) {

            int chunkIndex = resultObj.get("next_chunk_index").getAsInt();
            String chunkUrl = baseUrl + "/api/2.0/sql/statements/" + statementId
                    + "/result/chunks/" + chunkIndex;

            HttpRequest chunkReq = HttpRequest.newBuilder()
                    .uri(URI.create(chunkUrl))
                    .header("Authorization", "Bearer " + token)
                    .GET()
                    .timeout(Duration.ofMillis(config.getRequestTimeoutMs()))
                    .build();

            HttpResponse<String> chunkResp = httpClient.send(chunkReq, HttpResponse.BodyHandlers.ofString());
            if (chunkResp.statusCode() != 200) {
                logger.warn("Chunk {} fetch failed (HTTP {}), stopping pagination",
                        chunkIndex, chunkResp.statusCode());
                break;
            }

            JsonObject chunkJson = gson.fromJson(chunkResp.body(), JsonObject.class);
            extractRows(chunkJson, allRows);

            resultObj = chunkJson.has("result") && !chunkJson.get("result").isJsonNull()
                    ? chunkJson.getAsJsonObject("result") : null;
        }

        if (allRows.size() >= MAX_ROWS) {
            logger.warn("Query result truncated at {} rows (MAX_ROWS limit)", MAX_ROWS);
        }

        return allRows;
    }

    /**
     * Resolves a fresh Bearer token on every invocation (no caching per FR-9 / risk section).
     * <ul>
     *   <li>{@code bearer_token} mode: returns {@code config.getBearerToken()} directly (PAT / U2M).</li>
     *   <li>{@code service_principal} mode: POST to workspace OIDC for client_credentials grant.</li>
     *   <li>{@code account_id} mode: POST to account-level OIDC endpoint.</li>
     * </ul>
     */
    String resolveToken() throws Exception {
        if (config.isBearerTokenMode()) {
            String token = config.getBearerToken();
            if (token == null || token.isEmpty()) {
                throw new IllegalStateException("bearerToken is empty in bearer_token auth mode");
            }
            return token;
        }

        // Service principal or account_id: OAuth2 client_credentials grant
        String clientId = config.getOauthClientId();
        String clientSecret = config.getOauthClientSecret();
        if (clientId == null || clientId.isEmpty() || clientSecret == null || clientSecret.isEmpty()) {
            throw new IllegalStateException(
                    "oauthClientId and oauthClientSecret are required for service_principal auth mode");
        }

        String tokenUrl;
        String accountId = config.getAccountId();
        if (accountId != null && !accountId.isEmpty()) {
            // Account-level OIDC
            tokenUrl = "https://accounts.cloud.databricks.com/oidc/accounts/" + accountId + "/v1/token";
        } else {
            // Workspace-level OIDC
            tokenUrl = normalizeWorkspaceUrl(config.getWorkspaceUrl()) + "/oidc/v1/token";
        }

        // NOTE: Client ID and secret are from config, not user input — URL encoding for safety.
        String formBody = "grant_type=client_credentials"
                + "&client_id=" + java.net.URLEncoder.encode(clientId, StandardCharsets.UTF_8)
                + "&client_secret=" + java.net.URLEncoder.encode(clientSecret, StandardCharsets.UTF_8);

        HttpRequest tokenReq = HttpRequest.newBuilder()
                .uri(URI.create(tokenUrl))
                .header("Content-Type", "application/x-www-form-urlencoded")
                .POST(HttpRequest.BodyPublishers.ofString(formBody, StandardCharsets.UTF_8))
                .timeout(Duration.ofMillis(config.getConnectionTimeoutMs()))
                .build();

        HttpResponse<String> tokenResp = httpClient.send(tokenReq, HttpResponse.BodyHandlers.ofString());
        if (tokenResp.statusCode() != 200) {
            throw new RuntimeException("OAuth token request failed (HTTP "
                    + tokenResp.statusCode() + "): " + tokenResp.body());
        }

        JsonObject tokenJson = gson.fromJson(tokenResp.body(), JsonObject.class);
        if (!tokenJson.has("access_token")) {
            throw new RuntimeException("OAuth response missing access_token field");
        }
        return tokenJson.get("access_token").getAsString();
    }

    // ---- private helpers ----

    /** Extracts {@code data_array} rows from a statement result JSON and appends to {@code out}. */
    private void extractRows(JsonObject json, List<Object[]> out) {
        JsonObject resultObj = null;

        if (json.has("result") && !json.get("result").isJsonNull()) {
            resultObj = json.getAsJsonObject("result");
        } else if (json.has("data_array")) {
            // Chunk response — data_array at top level
            resultObj = json;
        }

        if (resultObj == null || !resultObj.has("data_array")
                || resultObj.get("data_array").isJsonNull()) {
            return;
        }

        JsonArray dataArray = resultObj.getAsJsonArray("data_array");
        for (JsonElement rowElement : dataArray) {
            if (out.size() >= MAX_ROWS) {
                break;
            }
            JsonArray rowArray = rowElement.getAsJsonArray();
            Object[] row = new Object[rowArray.size()];
            for (int i = 0; i < rowArray.size(); i++) {
                JsonElement cell = rowArray.get(i);
                row[i] = cell.isJsonNull() ? null : cell.getAsString();
            }
            out.add(row);
        }
    }

    private void cancelStatement(String baseUrl, String statementId, String token) {
        try {
            HttpRequest req = HttpRequest.newBuilder()
                    .uri(URI.create(baseUrl + "/api/2.0/sql/statements/" + statementId + "/cancel"))
                    .header("Authorization", "Bearer " + token)
                    .POST(HttpRequest.BodyPublishers.noBody())
                    .timeout(Duration.ofSeconds(5))
                    .build();
            httpClient.send(req, HttpResponse.BodyHandlers.discarding());
        } catch (Exception e) {
            logger.debug("Cancel statement {} failed (ignored): {}", statementId, e.getMessage());
        }
    }

    private static String normalizeWorkspaceUrl(String url) {
        if (url == null) return "";
        url = url.trim();
        if (!url.startsWith("http")) {
            url = "https://" + url;
        }
        while (url.endsWith("/")) {
            url = url.substring(0, url.length() - 1);
        }
        return url;
    }
}
