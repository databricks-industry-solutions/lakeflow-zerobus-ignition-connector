package com.example.ignition.zerobus.history;

import com.example.ignition.zerobus.ConfigModel;
import com.inductiveautomation.ignition.common.QualifiedPath;
import com.inductiveautomation.ignition.common.browsing.BrowseFilter;
import com.inductiveautomation.ignition.common.browsing.Results;
import com.inductiveautomation.ignition.common.browsing.Result;
import com.inductiveautomation.ignition.common.sqltags.history.Aggregate;
import com.inductiveautomation.ignition.common.util.TimelineSet;
import com.inductiveautomation.ignition.gateway.model.GatewayContext;
import com.inductiveautomation.ignition.gateway.model.ProfileStatus;
import com.inductiveautomation.ignition.gateway.sqltags.history.query.ColumnQueryDefinition;
import com.inductiveautomation.ignition.gateway.sqltags.history.query.HistoryQueryExecutor;
import com.inductiveautomation.ignition.gateway.sqltags.history.query.QueryController;
import com.inductiveautomation.historian.gateway.api.config.HistorianSettings;
import com.inductiveautomation.historian.gateway.legacy.LegacyTagHistoryProviderAdapter;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.ArrayList;
import java.util.Date;
import java.util.List;

/**
 * Ignition 8.3 TagHistoryProvider backed by Databricks Delta via the SQL Statement Execution API.
 *
 * Extends LegacyTagHistoryProviderAdapter (required for 8.3.3+ where getStorageEngine() was
 * removed from the TagHistoryProvider interface).
 *
 * Write path: tag history flows through ZerobusHistoryDataSink -> existing Zerobus pipeline.
 * Read path: createQuery() returns a ZerobusHistoryQueryExecutor that queries Databricks SQL.
 */
public class ZerobusTagHistoryProvider extends LegacyTagHistoryProviderAdapter<HistorianSettings> {

    private static final Logger logger = LoggerFactory.getLogger(ZerobusTagHistoryProvider.class);
    public static final String PROVIDER_NAME = "Zerobus";

    private final String name;
    private final ConfigModel config;
    private final DatabricksSqlClient sqlClient;

    public ZerobusTagHistoryProvider(GatewayContext context, String name, ConfigModel config) {
        super(context, name);
        this.name = name;
        this.config = config;
        this.sqlClient = new DatabricksSqlClient(config);
    }

    @Override
    public String getName() {
        return name;
    }

    @Override
    public void startup() throws Exception {
        logger.info("ZerobusTagHistoryProvider started: {}", name);
    }

    @Override
    public void shutdown() {
        logger.info("ZerobusTagHistoryProvider stopped: {}", name);
    }

    @Override
    public HistorianSettings getSettings() {
        return HistorianSettings.EMPTY;
    }

    @Override
    public ProfileStatus getStatus() {
        return ProfileStatus.RUNNING;
    }

    @Override
    public List<Aggregate> getAvailableAggregates() {
        return new ArrayList<>();
    }

    @Override
    public HistoryQueryExecutor createQuery(List<ColumnQueryDefinition> columns,
                                            QueryController controller) {
        logger.debug("createQuery: {} columns, queryId={}", columns.size(), controller.getQueryId());
        return new ZerobusHistoryQueryExecutor(config, columns, controller, sqlClient);
    }

    @Override
    public Results<? extends Result> browse(QualifiedPath path, BrowseFilter filter) {
        return new Results<>();
    }

    @Override
    public TimelineSet queryDensity(List<QualifiedPath> paths, Date start, Date end,
                                    String queryId) throws Exception {
        return new TimelineSet(new ArrayList<>());
    }
}
