package com.example.ignition.zerobus.web;

import com.example.ignition.zerobus.ZerobusGatewayHook;
import com.example.ignition.zerobus.ZerobusGatewayHookHolder;
import com.example.ignition.zerobus.ZerobusSettings;
import com.inductiveautomation.ignition.gateway.model.IgnitionWebApp;
import com.inductiveautomation.ignition.gateway.localdb.persistence.PersistenceSession;
import com.inductiveautomation.ignition.gateway.web.components.RecordEditForm;
import com.inductiveautomation.ignition.gateway.web.models.LenientResourceModel;
import com.inductiveautomation.ignition.gateway.web.pages.IConfigPage;
import org.apache.commons.lang3.tuple.Pair;
import org.apache.wicket.Application;
import simpleorm.dataset.SQuery;
import simpleorm.dataset.SRecordInstance;

import java.util.List;

/**
 * ZerobusSettingsPage - Gateway configuration page for Zerobus Connector settings.
 *
 * This page extends RecordEditForm to provide automatic form generation for the
 * ZerobusSettings PersistentRecord. Users can configure the module through the
 * Gateway web interface at: Config → System → Zerobus Connector
 *
 * The form automatically generates input fields for all PersistentRecord fields
 * with appropriate types (text inputs, checkboxes, number inputs, etc.) and
 * handles saving to the Gateway database.
 */
public class ZerobusSettingsPage extends RecordEditForm {
    private static final String I18N_BUNDLE = "zerobus";

    /**
     * Menu location for this config page in the Gateway navigation.
     * Format: Pair.of(categoryName, pageName)
     * Must match the name returned by getMenuLocation()
     * Using CONFIG_CATEGORY from ZerobusGatewayHook to place under Config → System section
     */
    public static final Pair<String, String> MENU_LOCATION =
        Pair.of(ZerobusGatewayHook.CONFIG_CATEGORY.getName(), "zerobus");

    /**
     * Constructor for the settings page.
     *
     * @param configPage The IConfigPage context provided by Ignition
     */
    public ZerobusSettingsPage(final IConfigPage configPage) {
        super(
            configPage,
            null,  // No parent record
            new org.apache.wicket.model.Model<String>(getPageTitle()),
            getOrCreateSettings()
        );
    }

    private static String getPageTitle() {
        try {
            // BundleUtil sub-bundles resolve via "bundleName.key" format (e.g. zerobus.Zerobus.nav.settings.panelTitle).
            String title = com.inductiveautomation.ignition.common.BundleUtil.get()
                .getString(I18N_BUNDLE + ".Zerobus.nav.settings.panelTitle");
            return title != null ? title : "Zerobus Connector Configuration";
        } catch (Exception e) {
            return "Zerobus Connector Configuration";
        }
    }

    /**
     * Get existing settings record or create a new one.
     * Since ZerobusSettings doesn't have a primary key, we query for any record
     * and create one if none exists.
     */
    private static ZerobusSettings getOrCreateSettings() {
        com.inductiveautomation.ignition.gateway.localdb.persistence.PersistenceInterface persistence =
            ((IgnitionWebApp) Application.get()).getContext().getPersistenceInterface();

        try {
            java.util.List<ZerobusSettings> records =
                persistence.query(new simpleorm.dataset.SQuery<>(ZerobusSettings.META));

            if (!records.isEmpty()) {
                return records.get(0);
            }
        } catch (Exception e) {
            // Fall through to create new record
        }

        // No existing record, create a new one
        return persistence.createNew(ZerobusSettings.META);
    }

    /**
     * Returns the menu location for this page in the Gateway navigation.
     * Must match the MENU_LOCATION constant.
     *
     * @return Pair of category name and page name
     */
    @Override
    public Pair<String, String> getMenuLocation() {
        return MENU_LOCATION;
    }

    @Override
    protected void onBeforeCommit(PersistenceSession session, List<SRecordInstance> records) throws Exception {
        // Preserve existing secret if the user leaves the field blank.
        for (SRecordInstance rec : records) {
            if (!(rec instanceof ZerobusSettings)) {
                continue;
            }
            ZerobusSettings zs = (ZerobusSettings) rec;
            String submitted = zs.getString(ZerobusSettings.OauthClientSecret);

            // For edits: blank means "no change"
            if (submitted == null || submitted.isEmpty() || "*****".equals(submitted) || "****".equals(submitted)) {
                // IMPORTANT: Do NOT issue a query here. PersistenceSession.queryOne(...) triggers a flush,
                // which will attempt to write the current (blank) value and can violate NOT NULL constraints.
                //
                // Use SimpleORM's optimistic/original value tracking instead.
                Object initialValueObj = zs.getInitialValue(ZerobusSettings.OauthClientSecret);
                String initialValue = initialValueObj != null ? String.valueOf(initialValueObj) : null;

                // If we have an existing secret, restore it so the DB never sees NULL/blank.
                if (initialValue != null && !initialValue.isEmpty()) {
                    zs.setString(ZerobusSettings.OauthClientSecret, initialValue);
                } else {
                    // If there is no existing secret, keep it empty; the module will treat config as invalid
                    // and keep services stopped until the user supplies a secret.
                    zs.setEmpty(ZerobusSettings.OauthClientSecret);
                }
            }
        }
        super.onBeforeCommit(session, records);
    }

    @Override
    protected void onAfterCommit(List<SRecordInstance> records) {
        // After the PersistentRecord save succeeds, apply it to the running module (ConfigModel)
        // so /system/zerobus/config and diagnostics reflect the UI immediately.
        try {
            ZerobusGatewayHook hook = ZerobusGatewayHookHolder.get();
            if (hook != null) {
                for (SRecordInstance rec : records) {
                    if (rec instanceof ZerobusSettings) {
                        // IMPORTANT: Do not call hook.saveConfiguration(...) from this callback.
                        // Ignition's RecordEditForm commit flow already has a PersistenceSession open on this thread.
                        // Calling persistence APIs again can trigger "session already open" errors.
                        hook.applyRuntimeConfiguration(((ZerobusSettings) rec).toConfigModel());
                        break;
                    }
                }
            }
        } catch (Exception ignored) {
            // Avoid breaking the config UI flow; errors will be visible in gateway logs via hook.saveConfiguration().
        }
        super.onAfterCommit(records);
    }
}
