package com.example.ignition.zerobus.web;

import com.inductiveautomation.ignition.gateway.web.pages.IConfigPage;

/**
 * Config UI nav target: redirects to the Diagnostics section on the HTML configuration page.
 */
public class ZerobusDiagnosticsRedirectPanel extends RedirectConfigPanel {
    public ZerobusDiagnosticsRedirectPanel(IConfigPage configPage) {
        super();
    }

    @Override
    protected String getTargetUrl() {
        return "/system/zerobus/configure#diagnosticsSection";
    }
}


