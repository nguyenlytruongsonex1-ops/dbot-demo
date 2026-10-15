-- Kịch bản: correlated_subquery (truy vấn con tương quan chạy lặp cho từng dòng)
-- Nguồn: chuyển từ kịch bản 2 trong dự án "LLM As DBA" của Nhóm 3 (bản gốc trên MySQL).
-- Mô tả: đếm đơn hàng có giá trị cao hơn trung bình các đơn của chính khách hàng đó.
--        Truy vấn con phụ thuộc vào o_custkey của dòng ngoài, nên PostgreSQL chạy lại
--        truy vấn con (SubPlan) cho từng đơn hàng, mỗi lần quét toàn bảng orders.
-- Dấu hiệu mong đợi: một phiên active chạy lâu (khoảng 30 đến 60 giây), dùng CPU,
--        EXPLAIN có dòng "SubPlan" nằm trong Filter.
-- Cách xử lý mong đợi: viết lại bằng JOIN với bảng tạm GROUP BY o_custkey (unnesting),
--        hoặc tạo index trên orders(o_custkey).
SELECT count(*) AS so_don
FROM tpch.orders o
WHERE o.o_orderkey <= 40000
  AND o.o_totalprice > (SELECT avg(o2.o_totalprice)
                        FROM tpch.orders o2
                        WHERE o2.o_custkey = o.o_custkey);
