# Chờ khóa (lock contention)

## Dấu hiệu
- pg_stat_activity có phiên wait_event_type = Lock.
- pg_locks có dòng granted = false.
- pg_blocking_pids(pid) trả về pid của phiên đang chặn.

## Nguyên nhân thường gặp
- Một transaction cập nhật dòng rồi không commit lâu (ứng dụng ngủ, chờ người dùng, lỗi logic).
- Hai transaction cập nhật cùng dòng theo thứ tự khác nhau.

## Cách xử lý
- Xác định phiên chặn: SELECT pid, pg_blocking_pids(pid) FROM pg_stat_activity;
- Nếu cần, kết thúc phiên chặn: SELECT pg_terminate_backend(blocking_pid);
- Đặt lock_timeout cho ứng dụng: SET lock_timeout = '5s';
- Giữ transaction ngắn, không gọi dịch vụ bên ngoài trong transaction.
