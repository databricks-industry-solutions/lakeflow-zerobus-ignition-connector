"""
Zerobus Ingest SDK - Local connectivity test.

Sends 10 JSON records to daveok.default.zerobus_test via the
Zerobus direct-write connector (gRPC) from the local machine.

Set DATABRICKS_CLIENT_ID and DATABRICKS_CLIENT_SECRET in the environment
(or use a .env file in this dir, not committed).
"""

import os
import time
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
TABLE_NAME = os.environ.get("ZEROBUS_TARGET_TABLE", "daveok.default.zerobus_test")
CLIENT_ID = os.environ.get("DATABRICKS_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("DATABRICKS_CLIENT_SECRET", "")
# -----------------------------------------------------------------------------

NUM_RECORDS = 10


def main():
    if not CLIENT_ID or not CLIENT_SECRET:
        raise SystemExit(
            "Set DATABRICKS_CLIENT_ID and DATABRICKS_CLIENT_SECRET in the environment (e.g. from .env)."
        )
    print(f"[1/4] Initialising Zerobus SDK")
    print(f"       Endpoint : {SERVER_ENDPOINT}")
    print(f"       Workspace: {WORKSPACE_URL}")
    print(f"       Table    : {TABLE_NAME}")
    print()

    sdk = ZerobusSdk(SERVER_ENDPOINT, WORKSPACE_URL)

    print(f"[2/4] Creating stream (OAuth M2M auth) ...")
    table_properties = TableProperties(TABLE_NAME)
    options = StreamConfigurationOptions(record_type=RecordType.JSON)
    stream = sdk.create_stream(CLIENT_ID, CLIENT_SECRET, table_properties, options)
    print(f"       Stream created successfully!\n")

    print(f"[3/4] Ingesting {NUM_RECORDS} records ...")
    t0 = time.time()
    try:
        for i in range(NUM_RECORDS):
            record = {
                "device_name": f"local-test-sensor-{i}",
                "temp": 20 + i,
                "humidity": 50 + i,
            }
            ack = stream.ingest_record(record)
            ack.wait_for_ack()
            print(f"       Record {i+1}/{NUM_RECORDS} acknowledged")
    finally:
        stream.close()

    elapsed = time.time() - t0
    print(f"\n[4/4] Done! {NUM_RECORDS} records ingested in {elapsed:.2f}s")
    print(f"       Verify with:")
    print(f"       SELECT * FROM {TABLE_NAME} ORDER BY device_name")


if __name__ == "__main__":
    main()
