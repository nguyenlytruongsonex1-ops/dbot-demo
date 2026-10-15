-- Kịch bản: lock_waiter (phiên bị kẹt vì chờ khóa)
-- Nguồn: tương ứng kịch bản 3 (tranh chấp khóa) trong dự án "LLM As DBA" của Nhóm 3.
-- Mô tả: cập nhật cùng đơn hàng o_orderkey = 1 mà lock_holder đang giữ.
--        Chạy lock_holder trước, rồi chạy kịch bản này.
-- Dấu hiệu mong đợi: phiên có wait_event_type = 'Lock',
--        pg_blocking_pids() trả về pid của lock_holder.
-- Cách xử lý mong đợi: kết thúc phiên đang giữ khóa, đặt lock_timeout
--        cho ứng dụng để không chờ vô hạn.
UPDATE tpch.orders SET o_totalprice = o_totalprice - 1 WHERE o_orderkey = 1;
