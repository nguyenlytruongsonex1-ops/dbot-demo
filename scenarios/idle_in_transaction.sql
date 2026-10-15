-- Kịch bản: idle_in_transaction (transaction mở nhưng không làm gì)
-- Mô tả: mở transaction, cập nhật đơn hàng o_orderkey = 2 rồi chờ 90 giây mới commit,
--        mô phỏng ứng dụng quên commit.
-- Dấu hiệu mong đợi: phiên giữ transaction rất lâu (xact_start cũ),
--        giữ khóa và cản VACUUM dọn dòng chết.
-- Cách xử lý mong đợi: đặt idle_in_transaction_session_timeout,
--        sửa ứng dụng để commit sớm, hủy phiên nếu cần.
BEGIN;
UPDATE tpch.orders SET o_comment = o_comment WHERE o_orderkey = 2;
SELECT pg_sleep(90);
COMMIT;
