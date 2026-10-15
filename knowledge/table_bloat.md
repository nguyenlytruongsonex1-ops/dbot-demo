# Bảng phình to (bloat)

## Dấu hiệu
- n_dead_tup trong pg_stat_user_tables rất lớn so với n_live_tup.
- Kích thước bảng tăng nhiều dù số dòng thật không đổi.
- Autovacuum bị tắt (reloptions có autovacuum_enabled=false) hoặc chạy không kịp.

## Nguyên nhân thường gặp
- UPDATE hoặc DELETE hàng loạt. Mỗi UPDATE tạo một phiên bản dòng mới, dòng cũ thành dòng chết.
- Autovacuum bị tắt hoặc bị transaction dài chặn.

## Cách xử lý
- Dọn dòng chết: VACUUM (ANALYZE) tpch.lineitem;
- Bật lại autovacuum: ALTER TABLE tpch.lineitem RESET (autovacuum_enabled);
- Muốn trả lại dung lượng cho hệ điều hành: VACUUM FULL (khóa bảng) hoặc pg_repack.
