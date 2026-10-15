-- Kịch bản: missing_index (thiếu index làm truy vấn chậm)
-- Mô tả: tìm các dòng hàng (lineitem) theo l_partkey 10000 lần. Cột này không có index,
--        nên mỗi lần tìm PostgreSQL phải quét toàn bảng lineitem (Seq Scan).
-- Dấu hiệu mong đợi: pg_stat_statements có câu SELECT trên lineitem được gọi rất nhiều lần,
--        mỗi lần đọc hàng nghìn block, EXPLAIN cho thấy Seq Scan on lineitem.
-- Cách xử lý mong đợi: CREATE INDEX ON tpch.lineitem(l_partkey);
-- Thời gian chạy: vài phút (tùy máy). Bấm Dừng để kết thúc sớm.
DO $$
DECLARE
  qty numeric;
BEGIN
  FOR i IN 1..10000 LOOP
    SELECT sum(l_quantity) INTO qty
    FROM tpch.lineitem
    WHERE l_partkey = 1 + (random() * 19999)::int;
  END LOOP;
END $$;
