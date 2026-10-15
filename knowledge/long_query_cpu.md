# Query chạy lâu và CPU cao

## Dấu hiệu
- pg_stat_activity có phiên state = active, query_start cách đây nhiều giây.
- wait_event_type rỗng nghĩa là phiên đang dùng CPU, không chờ I/O hay khóa.
- pg_stat_statements có câu lệnh với total_exec_time lớn nhất.

## Nguyên nhân thường gặp
- Query tính toán nặng trên toàn bảng (hàm toán học, DISTINCT, sắp xếp lớn).
- Vòng lặp trong hàm PL/pgSQL gọi đi gọi lại một query quét toàn bảng.
- Thiếu index nên phải quét và lọc hàng triệu dòng.

## Cách điều tra
- Xem câu SQL và thời gian chạy trong pg_stat_activity.
- Chạy EXPLAIN để xem kế hoạch thực thi, chú ý Seq Scan và Sort.

## Cách xử lý
- Hủy query đang chạy: SELECT pg_cancel_backend(pid);
- Đặt giới hạn: ALTER ROLE app_user SET statement_timeout = '30s';
- Viết lại query, tính trước kết quả vào bảng tổng hợp hoặc materialized view.
