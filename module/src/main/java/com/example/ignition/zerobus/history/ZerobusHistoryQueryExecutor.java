package com.example.ignition.zerobus.history;

import com.example.ignition.zerobus.ConfigModel;
import com.inductiveautomation.ignition.common.model.values.BasicQualifiedValue;
import com.inductiveautomation.ignition.common.model.values.QualifiedValue;
import com.inductiveautomation.ignition.common.sqltags.model.types.DataQuality;
import com.inductiveautomation.ignition.common.sqltags.model.types.DataTypeClass;
import com.inductiveautomation.ignition.gateway.sqltags.history.query.ColumnQueryDefinition;
import com.inductiveautomation.ignition.gateway.sqltags.history.query.HistoryQueryExecutor;
import com.inductiveautomation.ignition.gateway.sqltags.history.query.QueryController;
import com.inductiveautomation.ignition.gateway.sqltags.history.query.columns.NonCalculatingResultNode;
import com.inductiveautomation.ignition.gateway.sqltags.history.query.columns.ResultNode;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.ArrayList;
import java.util.Date;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * HistoryQueryExecutor that fetches tag history from Databricks Delta via the
 * SQL Statement Execution REST API.
 *
 * Queries: SELECT tag_path, event_time, numeric_value, quality_code
 *          FROM {catalog}.{schema}.raw_tags
 *          WHERE tag_path IN (...) AND event_time BETWEEN ... AND ...
 *          ORDER BY event_time ASC LIMIT 10000
 */
public class ZerobusHistoryQueryExecutor implements HistoryQueryExecutor {

    private static final Logger logger = LoggerFactory.getLogger(ZerobusHistoryQueryExecutor.class);
    private static final int MAX_ROWS = 10_000;

    private static final int COL_TAG_PATH = 0;
    private static final int COL_EVENT_TIME = 1;
    private static final int COL_NUMERIC_VALUE = 2;
    private static final int COL_QUALITY_CODE = 3;

    private final ConfigModel config;
    private final List<ColumnQueryDefinition> columns;
    private final QueryController controller;
    private final DatabricksSqlClient sqlClient;
    private final List<NonCalculatingResultNode> columnNodes;

    private boolean hasMore = true;
    private long maxTimestampMs = -1L;

    public ZerobusHistoryQueryExecutor(ConfigModel config,
                                       List<ColumnQueryDefinition> columns,
                                       QueryController controller,
                                       DatabricksSqlClient sqlClient) {
        this.config = config;
        this.columns = columns;
        this.controller = controller;
        this.sqlClient = sqlClient;

        long blockSize = controller.getBlockSize();
        boolean rawMode = blockSize <= 0;

        this.columnNodes = new ArrayList<>(columns.size());
        for (ColumnQueryDefinition col : columns) {
            String colName = col.getPath().getLastPathComponent();
            NonCalculatingResultNode node = new NonCalculatingResultNode(colName, rawMode, DataTypeClass.Float);
            columnNodes.add(node);
        }
    }

    @Override
    public List<? extends ResultNode> getColumnNodes() {
        return columnNodes;
    }

    @Override
    public void initialize() throws Exception {
    }

    @Override
    public int getEffectiveWindowSizeMS() {
        return 1000;
    }

    @Override
    public void startReading() throws Exception {
        Date startDate = controller.getQueryParameters().getStartDate();
        Date endDate = controller.getQueryParameters().getEndDate();
        long startMicros = startDate.getTime() * 1000L;
        long endMicros = endDate.getTime() * 1000L;

        String sql = buildSql(startMicros, endMicros);
        logger.debug("startReading: executing SQL for {} columns", columns.size());

        List<Object[]> resultRows;
        try {
            resultRows = sqlClient.executeQuery(sql, config.getRequestTimeoutMs());
            logger.debug("startReading: received {} rows from Databricks", resultRows.size());
        } catch (Exception e) {
            logger.error("startReading: Databricks SQL query failed", e);
            resultRows = new ArrayList<>();
        }

        // Map tag paths to column indices
        Map<String, Integer> pathToIndex = new HashMap<>();
        for (int i = 0; i < columns.size(); i++) {
            String path = columns.get(i).getPath().toString();
            pathToIndex.put(path, i);
            String lastComp = columns.get(i).getPath().getLastPathComponent();
            pathToIndex.putIfAbsent(lastComp, i);
        }

        // Distribute rows to columns
        @SuppressWarnings("unchecked")
        List<QualifiedValue>[] valuesByColumn = new List[columns.size()];
        for (int i = 0; i < columns.size(); i++) {
            valuesByColumn[i] = new ArrayList<>();
        }

        for (Object[] row : resultRows) {
            if (row == null || row.length < 4) continue;

            String tagPath = row[COL_TAG_PATH] != null ? (String) row[COL_TAG_PATH] : "";
            String eventTimeS = row[COL_EVENT_TIME] != null ? (String) row[COL_EVENT_TIME] : null;
            String numValueS = row[COL_NUMERIC_VALUE] != null ? (String) row[COL_NUMERIC_VALUE] : null;

            if (eventTimeS == null || numValueS == null) continue;

            long eventTimeMicros;
            double numericValue;
            try {
                eventTimeMicros = Long.parseLong(eventTimeS);
                numericValue = Double.parseDouble(numValueS);
            } catch (NumberFormatException e) {
                continue;
            }

            long eventTimeMs = eventTimeMicros / 1000L;
            if (eventTimeMs > maxTimestampMs) {
                maxTimestampMs = eventTimeMs;
            }

            String qualityS = row[COL_QUALITY_CODE] != null ? (String) row[COL_QUALITY_CODE] : null;
            int qualityCode = 192;
            if (qualityS != null) {
                try { qualityCode = Integer.parseInt(qualityS); } catch (NumberFormatException ignored) {}
            }
            DataQuality quality = qualityCode >= 192 ? DataQuality.GOOD_DATA : DataQuality.OPC_BAD_DATA;

            Integer colIdx = pathToIndex.get(tagPath);
            if (colIdx == null) {
                // Try matching by last path component
                for (Map.Entry<String, Integer> entry : pathToIndex.entrySet()) {
                    if (tagPath.endsWith(entry.getKey())) {
                        colIdx = entry.getValue();
                        break;
                    }
                }
            }
            if (colIdx != null) {
                valuesByColumn[colIdx].add(new BasicQualifiedValue(numericValue, quality, new Date(eventTimeMs)));
            }
        }

        // Push values into result nodes
        for (int i = 0; i < columns.size(); i++) {
            if (!valuesByColumn[i].isEmpty()) {
                columnNodes.get(i).put(valuesByColumn[i]);
            }
        }

        if (maxTimestampMs < 0) {
            maxTimestampMs = endDate.getTime();
        }
    }

    @Override
    public void endReading() {
    }

    @Override
    public boolean hasMore() {
        return hasMore;
    }

    @Override
    public long nextTime() {
        return Long.MAX_VALUE;
    }

    @Override
    public long processData() throws Exception {
        hasMore = false;
        return maxTimestampMs;
    }

    private String buildSql(long startMicros, long endMicros) {
        String table = config.getCatalogName() + "." + config.getSchemaName() + "." + config.getTableName();

        StringBuilder whereClause = new StringBuilder();
        for (int i = 0; i < columns.size(); i++) {
            if (i > 0) whereClause.append(", ");
            String path = columns.get(i).getPath().toString();
            whereClause.append("'").append(escapeSql(path)).append("'");
        }

        return "SELECT tag_path, event_time, numeric_value, quality_code FROM " + table
                + " WHERE tag_path IN (" + whereClause + ")"
                + " AND event_time >= " + startMicros
                + " AND event_time <= " + endMicros
                + " ORDER BY event_time ASC"
                + " LIMIT " + MAX_ROWS;
    }

    private static String escapeSql(String value) {
        if (value == null) return "";
        return value.replace("'", "''");
    }
}
