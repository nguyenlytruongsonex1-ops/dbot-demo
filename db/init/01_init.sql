-- Khởi tạo CSDL demo cho D-Bot Demo.
-- File này chạy một lần khi container postgres được tạo lần đầu.
-- Chỉ tạo cấu trúc bảng TPC-H. Dữ liệu (scale factor 0.1) do container
-- tpch-seed sinh bằng dbgen rồi nạp vào sau (xem seed/seed.sh).

CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
CREATE SCHEMA IF NOT EXISTS tpch;
SET search_path = tpch;

-- Chỉ có khóa chính. Cố ý KHÔNG tạo index phụ (ví dụ trên l_partkey,
-- o_custkey) để các kịch bản thiếu index có tác dụng.
CREATE TABLE region   (r_regionkey int PRIMARY KEY, r_name char(25), r_comment varchar(152));
CREATE TABLE nation   (n_nationkey int PRIMARY KEY, n_name char(25), n_regionkey int, n_comment varchar(152));
CREATE TABLE part     (p_partkey int PRIMARY KEY, p_name varchar(55), p_mfgr char(25), p_brand char(10),
                       p_type varchar(25), p_size int, p_container char(10), p_retailprice numeric(15,2),
                       p_comment varchar(23));
CREATE TABLE supplier (s_suppkey int PRIMARY KEY, s_name char(25), s_address varchar(40), s_nationkey int,
                       s_phone char(15), s_acctbal numeric(15,2), s_comment varchar(101));
CREATE TABLE partsupp (ps_partkey int, ps_suppkey int, ps_availqty int, ps_supplycost numeric(15,2),
                       ps_comment varchar(199), PRIMARY KEY (ps_partkey, ps_suppkey));
CREATE TABLE customer (c_custkey int PRIMARY KEY, c_name varchar(25), c_address varchar(40), c_nationkey int,
                       c_phone char(15), c_acctbal numeric(15,2), c_mktsegment char(10), c_comment varchar(117));
CREATE TABLE orders   (o_orderkey int PRIMARY KEY, o_custkey int, o_orderstatus char(1),
                       o_totalprice numeric(15,2), o_orderdate date, o_orderpriority char(15),
                       o_clerk char(15), o_shippriority int, o_comment varchar(79));
CREATE TABLE lineitem (l_orderkey int, l_partkey int, l_suppkey int, l_linenumber int,
                       l_quantity numeric(15,2), l_extendedprice numeric(15,2), l_discount numeric(15,2),
                       l_tax numeric(15,2), l_returnflag char(1), l_linestatus char(1),
                       l_shipdate date, l_commitdate date, l_receiptdate date,
                       l_shipinstruct char(25), l_shipmode char(10), l_comment varchar(44),
                       PRIMARY KEY (l_orderkey, l_linenumber));

-- User riêng để chạy kịch bản. Chỉ có quyền trên schema tpch.
-- Mỗi câu lệnh bị giới hạn 10 phút để tránh treo máy.
CREATE ROLE scenario_runner LOGIN PASSWORD 'scenario_pw';
GRANT USAGE, CREATE ON SCHEMA tpch TO scenario_runner;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA tpch TO scenario_runner;
-- Cần quyền chủ bảng để kịch bản bloat được tắt autovacuum và chạy VACUUM.
ALTER TABLE lineitem OWNER TO scenario_runner;
ALTER TABLE orders OWNER TO scenario_runner;
ALTER ROLE scenario_runner SET statement_timeout = '10min';
ALTER ROLE scenario_runner SET search_path = tpch, public;
