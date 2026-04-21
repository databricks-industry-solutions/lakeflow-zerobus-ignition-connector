package com.databricks.zerobus;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.IOException;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.Base64;
import java.util.function.Supplier;

/**
 * Overrides the Zerobus SDK's default workspace-level OIDC token exchange with
 * an account-level OIDC endpoint.
 *
 * On some Azure Databricks workspaces the workspace OIDC endpoint rejects
 * service principal credentials ({@code invalid_client}), but the same
 * credentials succeed at the account-level endpoint:
 * {@code https://accounts.azuredatabricks.net/oidc/accounts/{accountId}/v1/token}
 *
 * This class lives in {@code com.databricks.zerobus} so it can access the
 * package-private {@link ZerobusSdk#setStubFactory} method (same technique as
 * {@link BearerTokenStubFactory}).
 */
public class AccountOidcHelper extends ZerobusSdkStubFactory {

    private static final Logger logger = LoggerFactory.getLogger(AccountOidcHelper.class);

    private static final String AZURE_ACCOUNT_OIDC_TEMPLATE =
            "https://accounts.azuredatabricks.net/oidc/accounts/%s/v1/token";

    private final Supplier<String> tokenSupplier;

    private AccountOidcHelper(Supplier<String> tokenSupplier) {
        super();
        this.tokenSupplier = tokenSupplier;
    }

    @Override
    ZerobusGrpc.ZerobusStub createStubWithTokenSupplier(
            String endpoint, String tableName, Supplier<String> sdkTokenSupplier) {
        // Replace the SDK's workspace-level token supplier with our account-level one.
        return super.createStubWithTokenSupplier(endpoint, tableName, this.tokenSupplier);
    }

    /**
     * Configure a {@link ZerobusSdk} instance to use account-level OIDC for
     * token acquisition.  Must be called after construction and before
     * {@code createStream()}.
     *
     * @param sdk          the SDK instance to configure
     * @param accountId    Databricks account ID (UUID)
     * @param clientId     OAuth2 client ID (service principal application ID)
     * @param clientSecret OAuth2 client secret
     */
    public static void configure(ZerobusSdk sdk, String accountId,
                                 String clientId, String clientSecret) {
        String tokenUrl = String.format(AZURE_ACCOUNT_OIDC_TEMPLATE, accountId);
        logger.info("Configuring account-level OIDC: {}", tokenUrl);

        CachedTokenSupplier supplier = new CachedTokenSupplier(tokenUrl, clientId, clientSecret);
        sdk.setStubFactory(new AccountOidcHelper(supplier));
    }

    // ------------------------------------------------------------------
    // Token supplier with caching
    // ------------------------------------------------------------------

    /**
     * Thread-safe token supplier that caches OAuth tokens and refreshes them
     * before expiry.  Tokens are fetched from the account-level OIDC endpoint
     * using the standard OAuth2 Client Credentials grant with HTTP Basic auth.
     */
    static class CachedTokenSupplier implements Supplier<String> {

        private final String tokenUrl;
        private final String clientId;
        private final String clientSecret;

        private volatile String cachedToken;
        private volatile long expiresAtMs;

        // Refresh 5 minutes before expiry to avoid edge-case failures.
        private static final long REFRESH_MARGIN_MS = 5L * 60_000L;

        CachedTokenSupplier(String tokenUrl, String clientId, String clientSecret) {
            this.tokenUrl = tokenUrl;
            this.clientId = clientId;
            this.clientSecret = clientSecret;
        }

        @Override
        public String get() {
            if (cachedToken != null && System.currentTimeMillis() < expiresAtMs) {
                return cachedToken;
            }
            synchronized (this) {
                // Double-check after acquiring lock.
                if (cachedToken != null && System.currentTimeMillis() < expiresAtMs) {
                    return cachedToken;
                }
                return refresh();
            }
        }

        private String refresh() {
            try {
                logger.debug("Fetching account-level OIDC token from {}", tokenUrl);

                HttpURLConnection conn = (HttpURLConnection) new URL(tokenUrl).openConnection();
                conn.setRequestMethod("POST");
                conn.setDoOutput(true);
                conn.setConnectTimeout(10_000);
                conn.setReadTimeout(10_000);

                // HTTP Basic auth: clientId:clientSecret
                String credentials = clientId + ":" + clientSecret;
                String encoded = Base64.getEncoder().encodeToString(
                        credentials.getBytes(StandardCharsets.UTF_8));
                conn.setRequestProperty("Authorization", "Basic " + encoded);
                conn.setRequestProperty("Content-Type", "application/x-www-form-urlencoded");

                byte[] body = "grant_type=client_credentials&scope=all-apis"
                        .getBytes(StandardCharsets.UTF_8);
                conn.setRequestProperty("Content-Length", String.valueOf(body.length));

                try (OutputStream os = conn.getOutputStream()) {
                    os.write(body);
                }

                int status = conn.getResponseCode();
                if (status != 200) {
                    String errBody = readStream(conn.getErrorStream());
                    throw new IOException("Account OIDC token request failed (HTTP " + status + "): " + errBody);
                }

                String responseBody = readStream(conn.getInputStream());
                // Minimal JSON parsing - avoid pulling in a JSON library just for this.
                cachedToken = extractJsonString(responseBody, "access_token");
                long expiresIn = extractJsonLong(responseBody, "expires_in", 3600);
                expiresAtMs = System.currentTimeMillis() + (expiresIn * 1000L) - REFRESH_MARGIN_MS;

                logger.info("Account-level OIDC token acquired (expires_in={}s)", expiresIn);
                return cachedToken;

            } catch (IOException e) {
                throw new RuntimeException("Failed to fetch account-level OIDC token from " + tokenUrl, e);
            }
        }

        private static String readStream(java.io.InputStream is) throws IOException {
            if (is == null) return "";
            byte[] buf = new byte[4096];
            StringBuilder sb = new StringBuilder();
            int n;
            while ((n = is.read(buf)) != -1) {
                sb.append(new String(buf, 0, n, StandardCharsets.UTF_8));
            }
            is.close();
            return sb.toString();
        }

        /** Extract a string value from a flat JSON object (no nesting). */
        private static String extractJsonString(String json, String key) {
            String search = "\"" + key + "\"";
            int idx = json.indexOf(search);
            if (idx < 0) throw new RuntimeException("Missing '" + key + "' in OIDC response");
            int colon = json.indexOf(':', idx + search.length());
            int quote1 = json.indexOf('"', colon + 1);
            int quote2 = json.indexOf('"', quote1 + 1);
            return json.substring(quote1 + 1, quote2);
        }

        /** Extract a numeric value from a flat JSON object, with a default. */
        private static long extractJsonLong(String json, String key, long defaultValue) {
            String search = "\"" + key + "\"";
            int idx = json.indexOf(search);
            if (idx < 0) return defaultValue;
            int colon = json.indexOf(':', idx + search.length());
            int start = colon + 1;
            while (start < json.length() && json.charAt(start) == ' ') start++;
            int end = start;
            while (end < json.length() && Character.isDigit(json.charAt(end))) end++;
            if (end == start) return defaultValue;
            return Long.parseLong(json.substring(start, end));
        }
    }
}
