# Image dùng một lần: build dbgen của tpch-kit, sinh dữ liệu TPC-H và nạp vào PostgreSQL.
FROM postgres:16
RUN apt-get update && apt-get install -y --no-install-recommends build-essential git ca-certificates \
 && git clone --depth 1 https://github.com/gregrahn/tpch-kit /opt/tpch-kit \
 && make -C /opt/tpch-kit/dbgen MACHINE=LINUX DATABASE=POSTGRESQL \
 && apt-get purge -y build-essential git && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*
COPY seed.sh /seed.sh
ENTRYPOINT ["/seed.sh"]
