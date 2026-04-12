package com.databricks.zerobus;

import java.util.function.Supplier;

/**
 * Custom stub factory that bypasses the SDK's M2M OAuth token exchange
 * and instead injects a pre-obtained bearer token (PAT, U2M, etc.).
 *
 * This works because ZerobusSdkStubFactory and ZerobusSdk.setStubFactory()
 * are package-private in com.databricks.zerobus, so placing this class in
 * the same package grants access.
 *
 * When ZerobusSdk.createStream() is called, it internally builds a token
 * supplier from clientId/clientSecret and passes it to
 * stubFactory.createStubWithTokenSupplier(). We override that method to
 * substitute our own token supplier, making the clientId/clientSecret
 * params effectively unused for authentication.
 */
public class BearerTokenStubFactory extends ZerobusSdkStubFactory {

    private final Supplier<String> tokenSupplier;

    /**
     * @param tokenSupplier supplies the bearer token string (without "Bearer " prefix)
     */
    public BearerTokenStubFactory(Supplier<String> tokenSupplier) {
        super();
        this.tokenSupplier = tokenSupplier;
    }

    /**
     * Intercepts the SDK's call and replaces the SDK-generated token supplier
     * (which would do M2M client_credentials exchange) with our fixed supplier.
     */
    @Override
    ZerobusGrpc.ZerobusStub createStubWithTokenSupplier(
            String endpoint, String tableName, Supplier<String> sdkTokenSupplier) {
        // Ignore sdkTokenSupplier (the SDK's M2M token factory) and use ours instead.
        return super.createStubWithTokenSupplier(endpoint, tableName, this.tokenSupplier);
    }

    /**
     * Inject this factory into an existing ZerobusSdk instance.
     * Must be called before createStream().
     */
    public static void inject(ZerobusSdk sdk, Supplier<String> tokenSupplier) {
        sdk.setStubFactory(new BearerTokenStubFactory(tokenSupplier));
    }
}
