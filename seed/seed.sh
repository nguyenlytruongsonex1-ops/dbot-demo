#!/bin/sh
# Sinh dữ liệu TPC-H bằng dbgen rồi nạp vào PostgreSQL bằng COPY.
# Biến môi trường: PGHOST, PGUSER, PGPASSWORD, PGDATABASE, TPCH_SF (mặc định 0.1),
# DBGEN_DIR (thư mục chứa dbgen và dists.dss).
set -e
SF="${TPCH_SF:-0.1}"
DBGEN_DIR="${DBGEN_DIR:-/opt/tpch-kit/dbgen}"
OUT="${TPCH_OUT:-/tmp/tpch-data}"

N=$(psql -tAc "SELECT count(*) FROM tpch.region")
if [ "$N" -gt 0 ]; then
  echo "Dữ liệu TPC-H đã có, bỏ qua bước nạp."
  exit 0
fi

echo "Sinh dữ liệu TPC-H scale factor $SF ..."
mkdir -p "$OUT"
cd "$DBGEN_DIR"
DSS_PATH="$OUT" DSS_CONFIG="$DBGEN_DIR" ./dbgen -s "$SF" -f -q

for t in region nation part supplier partsupp customer orders lineitem; do
  echo "Nạp bảng $t ..."
  # Mỗi dòng của dbgen kết thúc bằng dấu |, cần bỏ đi trước khi COPY.
  sed 's/|$//' "$OUT/$t.tbl" | psql -q -c "\\copy tpch.$t FROM STDIN WITH (FORMAT text, DELIMITER '|')"
done
psql -q -c "ANALYZE" 
rm -rf "$OUT"
psql -tAc "SELECT 'lineitem: ' || count(*) FROM tpch.lineitem"
echo "Xong."
