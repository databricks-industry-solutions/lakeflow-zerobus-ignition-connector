package com.example.ignition.zerobus.web;

import com.inductiveautomation.ignition.gateway.web.pages.IConfigPage;

/**
 * Config UI nav target: redirects to the HTML configuration page served at /system/zerobus/configure.
 */
public class ZerobusConfigureRedirectPanel extends RedirectConfigPanel {
    public ZerobusConfigureRedirectPanel(IConfigPage configPage) {
        super();
    }

    @Override
    protected String getTargetUrl() {
        return "/system/zerobus/configure";
    }
}


