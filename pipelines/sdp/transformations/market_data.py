"""Market data tables - NEM prices and forecasts.

SDP tables for NEM dispatch prices and price forecasts.
"""

from pyspark import pipelines as dp
from pyspark.sql.types import DoubleType, StringType, StructField, StructType, TimestampType

from agl_analytics.market import generate_historical_prices, generate_price_forecast


@dp.table(
    name="nem_prices",
    comment="Historical NEM 5-minute dispatch prices",
)
@dp.expect("valid_interval", "interval_start IS NOT NULL AND interval_end IS NOT NULL AND interval_start < interval_end")
@dp.expect("valid_price", "price_aud_mwh IS NOT NULL")
def nem_prices():
    """Table: Historical NEM dispatch prices.

    Seeded from synthetic generator, append-only for incremental updates.
    """
    # Generate 30 days of historical prices
    prices = generate_historical_prices(days=30, region="NSW1")

    schema = StructType(
        [
            StructField("interval_start", TimestampType(), False),
            StructField("interval_end", TimestampType(), False),
            StructField("region", StringType(), False),
            StructField("price_aud_mwh", DoubleType(), False),
            StructField("demand_mw", DoubleType(), False),
        ]
    )

    return spark.createDataFrame(prices, schema)  # noqa: F821


@dp.materialized_view(
    name="price_forecast",
    comment="48-hour NEM price forecast (regenerated on each refresh)",
)
@dp.expect("valid_forecast_timestamp", "forecast_timestamp IS NOT NULL")
@dp.expect("valid_forecast_price", "forecast_price_aud_mwh IS NOT NULL")
def price_forecast():
    """Materialized view: 48-hour price forecast.

    Full refresh on each pipeline run - generates new synthetic forecast.
    """
    # Generate 48-hour forecast
    forecast = generate_price_forecast(hours=48, region="NSW1")

    schema = StructType(
        [
            StructField("forecast_timestamp", TimestampType(), False),
            StructField("target_interval", TimestampType(), False),
            StructField("region", StringType(), False),
            StructField("forecast_price_aud_mwh", DoubleType(), False),
            StructField("confidence", StringType(), False),
        ]
    )

    # Add forecast_timestamp to each record
    from datetime import datetime

    now = datetime.now()
    records = [
        {
            "forecast_timestamp": now,
            "target_interval": r["target_interval"],
            "region": r["region"],
            "forecast_price_aud_mwh": r["forecast_price_aud_mwh"],
            "confidence": r["confidence"],
        }
        for r in forecast
    ]

    return spark.createDataFrame(records, schema)  # noqa: F821
