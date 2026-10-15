# Thiếu index

## Dấu hiệu
- seq_scan của một bảng lớn tăng nhanh trong pg_stat_user_tables, idx_scan gần như không đổi.
- EXPLAIN cho thấy Seq Scan kèm Filter trên cột trong mệnh đề WHERE.
- pg_stat_statements có câu SELECT được gọi nhiều lần, thời gian trung bình cao.

## Nguyên nhân thường gặp
- Cột dùng để lọc hoặc join không có index.
- Có index nhưng điều kiện dùng hàm hoặc ép kiểu nên không dùng được index.

## Cách xử lý
- Tạo index trên cột lọc, nên dùng CONCURRENTLY để không khóa bảng:
  CREATE INDEX CONCURRENTLY idx_lineitem_partkey ON tpch.lineitem(l_partkey);
- Sau khi tạo, chạy ANALYZE và kiểm tra lại bằng EXPLAIN.
- Có thể thử trước bằng extension hypopg (index giả định).
