import pandas as pd

# =========================
# SETTINGS
# =========================

# 5 complete Normal traces
# 5 complete Anomaly traces
NORMAL_BLOCKS = 5
ANOMALY_BLOCKS = 5

HDFS_FILE = "HDFS_LOGCOLLECTOR.csv"
LABEL_FILE = "anomaly_label.csv"
OUTPUT_FILE = "demo.csv"

CHUNK_SIZE = 100000


# =========================
# READ ANOMALY LABEL FILE
# =========================

print("Reading anomaly_label.csv...")

labels = pd.read_csv(LABEL_FILE, dtype=str)

labels.columns = labels.columns.str.strip()
labels["BlockId"] = labels["BlockId"].str.strip()
labels["Label"] = labels["Label"].str.strip()

labels = labels.drop_duplicates(subset=["BlockId"])


# =========================
# SELECT 5 NORMAL BLOCK IDS
# =========================

normal_ids = (
    labels[
        labels["Label"].str.lower() == "normal"
    ]["BlockId"]
    .drop_duplicates()
    .head(NORMAL_BLOCKS)
    .tolist()
)


# =========================
# SELECT 5 ANOMALY BLOCK IDS
# =========================

anomaly_ids = (
    labels[
        labels["Label"].str.lower() == "anomaly"
    ]["BlockId"]
    .drop_duplicates()
    .head(ANOMALY_BLOCKS)
    .tolist()
)


selected_ids = normal_ids + anomaly_ids


print("\nSelected Normal Block IDs:")
for block in normal_ids:
    print(block)

print("\nSelected Anomaly Block IDs:")
for block in anomaly_ids:
    print(block)


# =========================
# READ HDFS FILE IN CHUNKS
# =========================

print("\nSearching HDFS_LOGCOLLECTOR.csv...")
print("Please wait. The file is large.")

matched_rows = []

for chunk_number, chunk in enumerate(
    pd.read_csv(
        HDFS_FILE,
        dtype=str,
        chunksize=CHUNK_SIZE
    )
):

    chunk.columns = chunk.columns.str.strip()

    if "block_id" not in chunk.columns:
        print("\nERROR: Cannot find block_id column.")
        print("Columns found:")
        print(chunk.columns.tolist())
        exit()

    chunk["block_id"] = chunk["block_id"].str.strip()

    matches = chunk[
        chunk["block_id"].isin(selected_ids)
    ].copy()

    if not matches.empty:
        matched_rows.append(matches)

    print(f"Processed chunk {chunk_number + 1}", end="\r")


# =========================
# CHECK RESULTS
# =========================

if len(matched_rows) == 0:
    print("\nERROR: No matching block IDs found.")
    exit()


# =========================
# COMBINE MATCHED ROWS
# =========================

demo = pd.concat(
    matched_rows,
    ignore_index=True
)


# =========================
# ADD NORMAL / ANOMALY LABEL
# =========================

label_for_merge = labels[
    ["BlockId", "Label"]
].rename(
    columns={"BlockId": "block_id"}
)

demo = demo.merge(
    label_for_merge,
    on="block_id",
    how="left",
    sort=False
)


# =========================
# KEEP ORIGINAL ORDER
# =========================

demo["line_id"] = pd.to_numeric(
    demo["line_id"],
    errors="coerce"
)

demo = demo.sort_values(
    by="line_id"
)


# =========================
# SAVE DEMO CSV
# =========================

demo.to_csv(
    OUTPUT_FILE,
    index=False
)


# =========================
# DISPLAY RESULTS
# =========================

print("\n\n==============================")
print("DEMO CSV CREATED SUCCESSFULLY")
print("==============================")

print("\nNormal traces selected:")
print(len(normal_ids))

print("\nAnomaly traces selected:")
print(len(anomaly_ids))

print("\nTotal traces:")
print(len(normal_ids) + len(anomaly_ids))

print("\nTotal rows copied:")
print(len(demo))

print("\nRows by label:")
print(demo["Label"].value_counts())

print("\nSaved as:")
print(OUTPUT_FILE)