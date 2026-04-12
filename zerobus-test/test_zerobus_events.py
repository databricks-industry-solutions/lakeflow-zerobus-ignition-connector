"""
Zerobus Ingest SDK - Test JSON write to raw_tags.

Sends 3 JSON records matching the full 18-column OTEvent schema to
agl_demo.ot.raw_tags. This isolates whether the 1521 error is
caused by the table (constraints / CDF / clustering) or by protobuf
stream registration.

If this passes → table is fine, issue is protobuf / Java SDK.
If this fails with 1521 → table constraints are the problem.

Set DATABRICKS_CLIENT_ID and DATABRICKS_CLIENT_SECRET in the environment
(or load from .env).
"""

import os
import time
import uuid
from zerobus.sdk.sync import ZerobusSdk
from zerobus.sdk.shared import RecordType, StreamConfigurationOptions, TableProperties

# --- Configuration (ZEROBUS_ENDPOINT or WORKSPACE_ID+DATABRICKS_REGION from .env) ---
def _zerobus_endpoint() -> str:
    e = os.environ.get("ZEROBUS_ENDPOINT")
    if e:
        return e
    wid, reg = os.environ.get("WORKSPACE_ID"), os.environ.get("DATABRICKS_REGION")
    if wid and reg:
        return f"{wid}.zerobus.{reg}.azuredatabricks.net"
    return "7405607216190670.zerobus.eastus2.azuredatabricks.net"


SERVER_ENDPOINT = _zerobus_endpoint()
WORKSPACE_URL = os.environ.get("DATABRICKS_HOST", "https://adb-7405607216190670.10.azuredatabricks.net")
TABLE_NAME = os.environ.get("ZEROBUS_TARGET_TABLE", "agl_demo.ot.raw_tags")
CLIENT_ID = os.environ.get("DATABRICKS_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("DATABRICKS_CLIENT_SECRET", "")
# -----------------------------------------------------------------------------

NUM_RECORDS = 3


def make_record(i: int) -> dict:
    """Build a JSON record matching the raw_tags 18-column schema exactly."""
    now_micros = int(time.time() * 1_000_000)
    return {
        "event_id": str(uuid.uuid4()),
        "event_time": now_micros,
        "tag_path": f"[test]ZerobusTest/sensor_{i}",
        "tag_provider": "test",
        "numeric_value": 20.0 + i,
        "string_value": "",
        "boolean_value": False,
        "quality": "Good",
        "quality_code": 192,
        "source_system": "zerobus-sdk-test",
        "ingestion_timestamp": now_micros,
        "data_type": "DOUBLE",
        "alarm_state": "",
        "alarm_priority": 0,
        "sdt_compressed": False,
        "compression_ratio": 0.0,
        "sdt_enabled": False,
        "batch_bytes_sent": 0,
    }


def main():
    if not CLIENT_ID or not CLIENT_SECRET:
        raise SystemExit(
            "Set DATABRICKS_CLIENT_ID and DATABRICKS_CLIENT_SECRET in the environment."
        )
    print(f"[1/4] Initialising Zerobus SDK")
    print(f"       Endpoint : {SERVER_ENDPOINT}")
    print(f"       Workspace: {WORKSPACE_URL}")
    print(f"       Table    : {TABLE_NAME}")
    print()

    sdk = ZerobusSdk(SERVER_ENDPOINT, WORKSPACE_URL)

    print(f"[2/4] Creating JSON stream to {TABLE_NAME} ...")
    table_properties = TableProperties(TABLE_NAME)
    options = StreamConfigurationOptions(record_type=RecordType.JSON)
    stream = sdk.create_stream(CLIENT_ID, CLIENT_SECRET, table_properties, options)
    print(f"       Stream created successfully!\n")

    print(f"[3/4] Ingesting {NUM_RECORDS} records ...")
    t0 = time.time()
    try:
        for i in range(NUM_RECORDS):
            record = make_record(i)
            ack = stream.ingest_record(record)
            ack.wait_for_ack()
            print(f"       Record {i+1}/{NUM_RECORDS} acknowledged (event_id={record['event_id'][:8]}...)")
    finally:
        stream.close()

    elapsed = time.time() - t0
    print(f"\n[4/4] Done! {NUM_RECORDS} records ingested in {elapsed:.2f}s")
    print(f"       Verify with:")
    print(f"       SELECT * FROM {TABLE_NAME} WHERE source_system = 'zerobus-sdk-test' ORDER BY event_time DESC LIMIT 10")


if __name__ == "__main__":
    main()
