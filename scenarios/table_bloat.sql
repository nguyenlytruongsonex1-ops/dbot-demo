-- Kịch bản: table_bloat (bảng phình to vì nhiều dòng chết)
-- Mô tả: tắt autovacuum trên bảng lineitem rồi cập nhật toàn bảng 3 lần.
--        Mỗi lần UPDATE tạo ra khoảng 600 nghìn phiên bản dòng cũ (dead tuple).
-- Dấu hiệu mong đợi: n_dead_tup trong pg_stat_user_tables rất cao,
--        kích thước bảng tăng gấp nhiều lần.
-- Cách xử lý mong đợi: VACUUM (ANALYZE) tpch.lineitem; bật lại autovacuum:
--        ALTER TABLE tpch.lineitem RESET (autovacuum_enabled);
-- Lưu ý: alert chỉ tự giải quyết sau khi chạy VACUUM.
--        Có thể chạy kịch bản fix_vacuum để dọn.
ALTER TABLE tpch.lineitem SET (autovacuum_enabled = false);
UPDATE tpch.lineitem SET l_comment = l_comment;
UPDATE tpch.lineitem SET l_comment = l_comment;
UPDATE tpch.lineitem SET l_comment = l_comment;
