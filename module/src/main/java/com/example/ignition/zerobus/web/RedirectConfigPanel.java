package com.example.ignition.zerobus.web;

import com.inductiveautomation.ignition.gateway.web.components.ConfigPanel;
import org.apache.wicket.request.flow.RedirectToUrlException;

/**
 * A tiny Gateway Config panel that redirects the browser to a URL.
 *
 * Ignition's left-nav config tabs are backed by {@link ConfigPanel} classes (not WebPages),
 * so we implement redirect behavior at panel construction time.
 */
public abstract class RedirectConfigPanel extends ConfigPanel {
    protected RedirectConfigPanel() {
        super();
        // Immediately redirect; no markup needed.
        throw new RedirectToUrlException(getTargetUrl());
    }

    /**
     * @return target URL for this config panel redirect. Typically an absolute-path URL like "/system/zerobus/configure".
     */
    protected abstract String getTargetUrl();
}


