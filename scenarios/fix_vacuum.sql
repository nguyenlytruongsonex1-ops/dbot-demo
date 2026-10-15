-- Kịch bản: fix_vacuum (dọn dẹp sau table_bloat)
-- Mô tả: đây không phải sự cố. File này dùng để dọn sau kịch bản table_bloat.
-- Tác dụng: bật lại autovacuum và chạy VACUUM để xóa dòng chết trên lineitem.
ALTER TABLE tpch.lineitem RESET (autovacuum_enabled);
VACUUM (ANALYZE) tpch.lineitem;
