-- Kịch bản: cpu_high (CPU tăng cao vì truy vấn tổng hợp nặng kiểu TPC-H)
-- Mô tả: một khối DO lặp lại 50 lần truy vấn tổng hợp giống TPC-H Q1 trên bảng lineitem
--        (khoảng 600 nghìn dòng), có thêm phép tính toán học cho từng dòng.
-- Dấu hiệu mong đợi: pg_stat_activity có một phiên active chạy lâu,
--        wait_event rỗng (tức là đang dùng CPU), CPU của container postgres tăng cao.
-- Cách xử lý mong đợi: tìm và hủy query (pg_cancel_backend), giới hạn statement_timeout,
--        tính trước kết quả vào bảng tổng hợp hoặc materialized view.
-- Thời gian chạy: khoảng 1 đến 3 phút. Bấm Dừng để kết thúc sớm.
DO $$
BEGIN
  FOR i IN 1..50 LOOP
    PERFORM l_returnflag, l_linestatus,
            sum(l_quantity), sum(l_extendedprice * (1 - l_discount) * (1 + l_tax)),
            avg(sqrt(l_extendedprice) * ln(l_quantity + 1)), count(DISTINCT l_partkey)
    FROM tpch.lineitem
    WHERE l_shipdate <= date '1998-12-01' - interval '90 days'
    GROUP BY l_returnflag, l_linestatus;
  END LOOP;
END $$;
