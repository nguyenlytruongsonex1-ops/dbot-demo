# Quá nhiều kết nối

## Dấu hiệu
- Số phiên trong pg_stat_activity gần bằng max_connections.
- Client mới nhận lỗi: sorry, too many clients already.

## Cách xử lý
- Dùng connection pool như PgBouncer.
- Đóng các phiên idle lâu, giảm số kết nối mỗi ứng dụng mở.
