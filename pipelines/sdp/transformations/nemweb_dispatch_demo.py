"""NEMWEB Dispatch Demo — Databricks 101 bolt-on.

Fetches LIVE 5-minute NEM dispatch data (spot prices + regional demand)
directly from AEMO's NEMWEB public feed on each pipeline refresh.

Two tables:
  - nem_dispatch_prices:  5-min spot prices across all 5 NEM regions (Bronze→Silver)
  - nem_dispatch_demand:  5-min regional demand & generation summary (Gold)

Data source: https://www.nemweb.com.au/REPORTS/CURRENT/DispatchIS_Reports/
Format: AEMO multi-record CSV inside ZIP files, published every 5 minutes.
"""

from pyspark import pipelines as dp
from pyspark.sql import functions as F
from pyspark.sql.types import (
    DoubleType,
    IntegerType,
    StringType,
    StructField,
    StructType,
    TimestampType,
)

# How many 5-min intervals to fetch (288 = 24 hours, 72 = 6 hours)
_LOOKBACK_FILES = 72

_NEMWEB_BASE = "https://www.nemweb.com.au"
_DISPATCH_DIR = "/REPORTS/CURRENT/DispatchIS_Reports/"


def _fetch_nemweb_dispatch() -> tuple[list[dict], list[dict]]:
    """Fetch recent dispatch ZIPs from NEMWEB, parse PRICE and REGIONSUM records."""
    import csv as csv_mod
    import io
    import re
    import urllib.request
    import zipfile

    # Discover available ZIP files
    req = urllib.request.Request(
        _NEMWEB_BASE + _DISPATCH_DIR,
        headers={"User-Agent": "Databricks-DLT/1.0"},
    )
    html = urllib.request.urlopen(req, timeout=30).read().decode("utf-8")
    zip_paths = re.findall(
        r'HREF="(' + re.escape(_DISPATCH_DIR) + r'PUBLIC_DISPATCHIS_[^"]+\.zip)"',
        html,
    )

    # Take only the most recent N files
    zip_paths = zip_paths[-_LOOKBACK_FILES:]
    print(f"NEMWEB: fetching {len(zip_paths)} dispatch files")

    prices = []
    regionsum = []

    for zpath in zip_paths:
        try:
            zreq = urllib.request.Request(
                _NEMWEB_BASE + zpath,
                headers={"User-Agent": "Databricks-DLT/1.0"},
            )
            zip_data = urllib.request.urlopen(zreq, timeout=15).read()

            with zipfile.ZipFile(io.BytesIO(zip_data)) as zf:
                for name in zf.namelist():
                    content = zf.read(name).decode("utf-8")
                    for line in content.strip().split("\n"):
                        if line.startswith("D,DISPATCH,PRICE,"):
                            parts = list(csv_mod.reader([line]))[0]
                            try:
                                prices.append(
                                    {
                                        "settlement_date": parts[4],
                                        "region_id": parts[6],
                                        "dispatch_interval": parts[7],
                                        "intervention": int(parts[8]),
                                        "rrp": float(parts[9]),
                                        "eep": float(parts[10]) if parts[10] else None,
                                    }
                                )
                            except (ValueError, IndexError):
                                pass
                        elif line.startswith("D,DISPATCH,REGIONSUM,"):
                            parts = list(csv_mod.reader([line]))[0]
                            try:
                                regionsum.append(
                                    {
                                        "settlement_date": parts[4],
                                        "region_id": parts[6],
                                        "dispatch_interval": parts[7],
                                        "intervention": int(parts[8]),
                                        "total_demand_mw": float(parts[9]),
                                        "available_generation_mw": float(parts[10]),
                                        "demand_forecast_mw": float(parts[12]),
                                        "net_interchange_mw": float(parts[15]),
                                    }
                                )
                            except (ValueError, IndexError):
                                pass
        except Exception as e:
            print(f"WARN: NEMWEB fetch failed for {zpath.split('/')[-1]}: {e}")

    print(f"NEMWEB: parsed {len(prices)} price records, {len(regionsum)} regionsum records")
    return prices, regionsum


_PRICE_SCHEMA = StructType(
    [
        StructField("settlement_date", StringType(), True),
        StructField("region_id", StringType(), True),
        StructField("dispatch_interval", StringType(), True),
        StructField("intervention", IntegerType(), True),
        StructField("rrp", DoubleType(), True),
        StructField("eep", DoubleType(), True),
    ]
)

_REGIONSUM_SCHEMA = StructType(
    [
        StructField("settlement_date", StringType(), True),
        StructField("region_id", StringType(), True),
        StructField("dispatch_interval", StringType(), True),
        StructField("intervention", IntegerType(), True),
        StructField("total_demand_mw", DoubleType(), True),
        StructField("available_generation_mw", DoubleType(), True),
        StructField("demand_forecast_mw", DoubleType(), True),
        StructField("net_interchange_mw", DoubleType(), True),
    ]
)




# ═══════════════════════════════════════════════════════════════════════════
# BRONZE → SILVER: 5-minute NEM spot prices
# ═══════════════════════════════════════════════════════════════════════════


@dp.table(
    name="nem_dispatch_prices",
    comment="Silver: live 5-minute NEM dispatch spot prices from NEMWEB. "
    "Regions: NSW1, QLD1, SA1, TAS1, VIC1.",
    cluster_by=["dispatch_timestamp", "region_id"],
)
@dp.expect(
    "has_region",
    "region_id IS NOT NULL",
)
@dp.expect(
    "has_price",
    "rrp IS NOT NULL",
)
@dp.expect(
    "valid_nem_region",
    "region_id IN ('NSW1', 'QLD1', 'SA1', 'TAS1', 'VIC1')",
)
@dp.expect_or_drop(
    "not_intervention",
    "intervention = 0",
)
@dp.expect(
    "price_within_nem_bounds",
    "rrp BETWEEN -1000 AND 17500",
)
def nem_dispatch_prices():
    """Live 5-minute NEM spot prices fetched from NEMWEB on each refresh.

    Filters out intervention pricing (intervention=1) via DROP ROW.
    NEM price cap is $17,500/MWh, floor is -$1,000/MWh.
    """
    prices, _ = _fetch_nemweb_dispatch()
    return (
        spark.createDataFrame(prices, schema=_PRICE_SCHEMA)  # noqa: F821
        .withColumn(
            "dispatch_timestamp",
            F.to_timestamp("settlement_date", "yyyy/MM/dd HH:mm:ss"),
        )
        .withColumn("ingested_at", F.current_timestamp())
    )


# ═══════════════════════════════════════════════════════════════════════════
# GOLD: regional demand & generation summary
# ═══════════════════════════════════════════════════════════════════════════


@dp.table(
    name="nem_dispatch_demand",
    comment="Silver: live 5-minute NEM regional demand and generation from NEMWEB.",
    cluster_by=["dispatch_timestamp", "region_id"],
)
@dp.expect(
    "has_region",
    "region_id IS NOT NULL",
)
@dp.expect(
    "has_demand",
    "total_demand_mw IS NOT NULL",
)
@dp.expect_or_drop(
    "not_intervention",
    "intervention = 0",
)
@dp.expect(
    "positive_demand",
    "total_demand_mw > 0",
)
def nem_dispatch_demand():
    """Live 5-minute NEM regional demand fetched from NEMWEB."""
    _, regionsum = _fetch_nemweb_dispatch()
    return (
        spark.createDataFrame(regionsum, schema=_REGIONSUM_SCHEMA)  # noqa: F821
        .withColumn(
            "dispatch_timestamp",
            F.to_timestamp("settlement_date", "yyyy/MM/dd HH:mm:ss"),
        )
        .withColumn("ingested_at", F.current_timestamp())
    )


@dp.materialized_view(
    name="nem_market_snapshot",
    comment="Gold: latest NEM market snapshot — price + demand per region.",
)
@dp.expect(
    "has_region",
    "region_id IS NOT NULL",
)
def nem_market_snapshot():
    """Gold view: join latest price + demand per region for a market-at-a-glance view."""
    from pyspark.sql.window import Window

    prices = spark.read.table("nem_dispatch_prices")  # noqa: F821
    demand = spark.read.table("nem_dispatch_demand")  # noqa: F821

    w = Window.partitionBy("region_id").orderBy(F.desc("dispatch_timestamp"))

    latest_prices = (
        prices.withColumn("rn", F.row_number().over(w))
        .filter(F.col("rn") == 1)
        .select(
            "region_id",
            F.col("dispatch_timestamp").alias("price_timestamp"),
            "rrp",
        )
    )

    latest_demand = (
        demand.withColumn("rn", F.row_number().over(w))
        .filter(F.col("rn") == 1)
        .select(
            "region_id",
            "total_demand_mw",
            "available_generation_mw",
            "net_interchange_mw",
        )
    )

    return latest_prices.join(latest_demand, on="region_id", how="inner")
