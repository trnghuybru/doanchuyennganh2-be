# Hướng dẫn chạy Migrations và Seed Data

## 📋 Tổng quan

File này hướng dẫn cách tạo và chạy migrations cho các bảng `exam_results` và `exam_answers`, cũng như cách chạy seed data.

## 🗄️ Các bảng mới được thêm

1. **exam_results**: Lưu kết quả bài thi của người dùng

   - `result_id`: ID kết quả (primary key)
   - `user_id`: ID người dùng làm bài
   - `exam_id`: ID đề thi
   - `total_questions`: Tổng số câu hỏi
   - `correct_answers`: Số câu trả lời đúng
   - `score`: Điểm số (0-100)
   - `status`: Trạng thái (in_progress, completed, abandoned)
   - `started_at`: Thời gian bắt đầu
   - `completed_at`: Thời gian hoàn thành

2. **exam_answers**: Lưu từng câu trả lời của người dùng
   - `answer_id`: ID câu trả lời (primary key)
   - `result_id`: ID kết quả bài thi
   - `question_id`: ID câu hỏi
   - `selected_choice_id`: ID lựa chọn đã chọn
   - `selected_choice_label`: Label của lựa chọn (A, B, C, D)
   - `is_correct`: Đánh dấu đúng/sai
   - `answered_at`: Thời gian trả lời

## 🚀 Các bước thực hiện

### Bước 1: Tạo Migration

Chạy lệnh sau để tạo migration mới cho các bảng `exam_results` và `exam_answers`:

```bash
# Windows PowerShell
python -m flask db migrate -m "Add exam_results and exam_answers tables"

# Hoặc nếu đã cài đặt flask CLI
flask db migrate -m "Add exam_results and exam_answers tables"
```

Lệnh này sẽ tạo một file migration mới trong thư mục `migrations/versions/`.

### Bước 2: Kiểm tra Migration

Mở file migration vừa tạo để kiểm tra xem có đúng không. File sẽ có tên dạng: `xxxxx_add_exam_results_and_exam_answers_tables.py`

### Bước 3: Chạy Migration

Sau khi kiểm tra, chạy lệnh sau để áp dụng migration vào database:

```bash
# Windows PowerShell
python -m flask db upgrade

# Hoặc
flask db upgrade
```

Lệnh này sẽ tạo các bảng `exam_results` và `exam_answers` trong database.

### Bước 4: Chạy Seed Data

Để tạo dữ liệu mẫu cho các bảng mới, chạy lệnh:

```bash
# Chỉ thêm dữ liệu mới (không xóa dữ liệu cũ)
python seed.py

# Hoặc xóa toàn bộ dữ liệu cũ và tạo lại từ đầu
python seed.py --reset
```

**Lưu ý:**

- Lệnh `python seed.py --reset` sẽ **XÓA TOÀN BỘ DỮ LIỆU** trong database và tạo lại từ đầu.
- Lệnh `python seed.py` chỉ thêm dữ liệu mới, không xóa dữ liệu cũ.

### Bước 5: Kiểm tra kết quả

Sau khi chạy seed, bạn sẽ thấy output tương tự:

```
✅ Đã tạo 8 users (email duy nhất).
✅ Đã tạo 12 tags (không trùng).
✅ Đã tạo 40 questions, 160 choices, 80 question_tags.
✅ Đã tạo 6 exams, 45 exam_questions.
✅ Đã tạo 12 media items.
✅ Đã tạo 3 question sets và gán 24 liên kết.
✅ Đã tạo 15 exam results.
✅ Đã tạo 120 exam answers.

🎉 Hoàn tất seed data:
   - Users: 8
   - Questions: 40
   - Exams: 6
   - Exam Results: 15
   - Exam Answers: 120
```

## 📝 Seed Data được tạo

Seed data sẽ tạo:

- **15 kết quả bài thi** với các trạng thái khác nhau:

  - `completed`: Đã hoàn thành với điểm số (60-100%)
  - `in_progress`: Đang làm dở (đã trả lời 30-70% câu hỏi)
  - `abandoned`: Đã bỏ dở (đã trả lời < 30% câu hỏi)

- **Câu trả lời** cho mỗi kết quả:
  - Mỗi kết quả có các câu trả lời tương ứng với số câu đã làm
  - Tỷ lệ chọn đúng: 60-80% để có điểm số hợp lý

## 🔍 Kiểm tra Database

Bạn có thể kiểm tra dữ liệu đã được tạo bằng cách query database:

```sql
-- Xem tất cả kết quả bài thi
SELECT * FROM exam_results;

-- Xem câu trả lời của một kết quả
SELECT * FROM exam_answers WHERE result_id = 'r_xxxxx';

-- Xem thống kê điểm số
SELECT
    status,
    COUNT(*) as count,
    AVG(score) as avg_score,
    MIN(score) as min_score,
    MAX(score) as max_score
FROM exam_results
GROUP BY status;
```

## ⚠️ Lưu ý

1. **Backup database** trước khi chạy `--reset` nếu có dữ liệu quan trọng
2. Đảm bảo database connection đã được cấu hình đúng trong file `.env` hoặc `config.py`
3. Nếu gặp lỗi khi chạy migration, kiểm tra:
   - Database đã được tạo chưa
   - Connection string có đúng không
   - Các bảng phụ thuộc (users, exams, questions, choices) đã tồn tại chưa

## 🐛 Xử lý lỗi

### Lỗi: "Table already exists"

Nếu bảng đã tồn tại, bạn có thể:

- Xóa bảng thủ công trong database
- Hoặc chạy `python seed.py --reset` để reset toàn bộ

### Lỗi: "Foreign key constraint fails"

Đảm bảo các bảng phụ thuộc (users, exams, questions, choices) đã có dữ liệu trước khi chạy seed.

### Lỗi: "Enum type already exists"

Nếu enum `exam_status` đã tồn tại, bạn có thể bỏ qua hoặc xóa enum cũ trong database.
