-- Kịch bản: lock_holder (giữ khóa dòng mà không commit)
-- Mô tả: mở transaction, cập nhật đơn hàng o_orderkey = 1 rồi ngủ 120 giây trước khi commit.
--        Chạy kịch bản này trước, sau đó chạy lock_waiter.
-- Dấu hiệu mong đợi: một phiên giữ transaction lâu và khóa dòng trên orders.
--        Khi có lock_waiter, pg_locks có khóa chưa được cấp (granted = false).
-- Cách xử lý mong đợi: tìm phiên chặn bằng pg_blocking_pids(), hủy phiên đó
--        bằng pg_terminate_backend(), và giữ transaction ngắn trong ứng dụng.
BEGIN;
UPDATE tpch.orders SET o_totalprice = o_totalprice + 1 WHERE o_orderkey = 1;
SELECT pg_sleep(120);
COMMIT;
