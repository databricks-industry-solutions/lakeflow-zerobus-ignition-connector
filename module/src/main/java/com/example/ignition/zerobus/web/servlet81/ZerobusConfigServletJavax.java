package com.example.ignition.zerobus.web.servlet81;

import com.example.ignition.zerobus.web.ZerobusServletHandler;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import javax.servlet.http.HttpServlet;
import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.nio.charset.Charset;
import java.nio.charset.StandardCharsets;

/**
 * Ignition 8.1/8.2 servlet implementation (javax.*).
 *
 * Endpoints:
 * - GET  /system/zerobus/health
 * - GET  /system/zerobus/diagnostics
 * - GET  /system/zerobus/config
 * - POST /system/zerobus/config
 * - POST /system/zerobus/test-connection
 * - POST /system/zerobus/ingest
 * - POST /system/zerobus/ingest/batch
 */
public class ZerobusConfigServletJavax extends HttpServlet {
    private static final Logger logger = LoggerFactory.getLogger(ZerobusConfigServletJavax.class);
    private static final String BASE_PATH = "/system/zerobus";

    @Override
    protected void doGet(HttpServletRequest req, HttpServletResponse resp) throws IOException {
        ZerobusServletHandler.Response out = ZerobusServletHandler.handle("GET", extractSubPath(req), null);
        respond(resp, out);
    }

    @Override
    protected void doPost(HttpServletRequest req, HttpServletResponse resp) throws IOException {
        String body = new String(req.getInputStream().readAllBytes(), pickCharset(req.getCharacterEncoding()));
        ZerobusServletHandler.Response out = ZerobusServletHandler.handle("POST", extractSubPath(req), body);
        respond(resp, out);
    }

    private static void respond(HttpServletResponse resp, ZerobusServletHandler.Response out) throws IOException {
        resp.setStatus(out.status);
        resp.setCharacterEncoding(StandardCharsets.UTF_8.name());
        resp.setContentType(out.contentType);
        resp.getWriter().write(out.body);
    }

    private static Charset pickCharset(String encoding) {
        if (encoding == null || encoding.isBlank()) {
            return StandardCharsets.UTF_8;
        }
        try {
            return Charset.forName(encoding);
        } catch (Exception e) {
            logger.debug("Unknown request characterEncoding '{}', defaulting to UTF-8", encoding);
            return StandardCharsets.UTF_8;
        }
    }

    /**
     * Ignition's web resource manager servlet mapping differs across versions.
     * Use the request URI to reliably compute the sub-path after /system/zerobus.
     */
    private static String extractSubPath(HttpServletRequest req) {
        try {
            String uri = req.getRequestURI();
            if (uri != null) {
                int idx = uri.indexOf(BASE_PATH);
                if (idx >= 0) {
                    String rest = uri.substring(idx + BASE_PATH.length());
                    return rest.isEmpty() ? "/" : rest;
                }
            }
        } catch (Exception e) {
            logger.debug("Failed extracting sub-path from request URI", e);
        }
        String pathInfo = req.getPathInfo();
        return (pathInfo == null || pathInfo.isBlank()) ? "/" : pathInfo;
    }
}


