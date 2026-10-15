# Transaction mở lâu không hoạt động

## Dấu hiệu
- state = idle in transaction, hoặc xact_start rất cũ so với hiện tại.
- Phiên giữ khóa, làm phiên khác phải chờ.
- VACUUM không dọn được dòng chết vì transaction cũ còn mở.

## Cách xử lý
- Đặt giới hạn: ALTER DATABASE dbot_demo SET idle_in_transaction_session_timeout = '60s';
- Sửa ứng dụng để commit hoặc rollback ngay sau khi xong việc.
- Kết thúc phiên nếu cần: SELECT pg_terminate_backend(pid);
