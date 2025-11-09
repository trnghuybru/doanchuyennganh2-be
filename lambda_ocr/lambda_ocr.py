import os
import json
from datetime import datetime, timezone
import requests
import boto3
from google import genai
from PIL import Image

# --- AWS clients/resources ---
S3 = boto3.client("s3")
DDB = boto3.resource("dynamodb")

# --- ENV ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")     # bắt buộc
DDB_TABLE      = os.getenv("DDB_TABLE")           # bắt buộc (VD: ExamQuestions)

# --- Prompts ---
SYSTEM_PROMPT = """
# VAI TRÒ (ROLE)
Bạn là chuyên gia OCR và phân tích đề thi với khả năng:
- Trích xuất văn bản chính xác từ hình ảnh đề thi đa ngôn ngữ
- Nhận dạng cấu trúc câu hỏi và phân loại theo taxonomy giáo dục
- Xử lý đa dạng định dạng đề thi (trắc nghiệm, tự luận, đọc hiểu)
---
# NHIỆM VỤ (TASK)

## 1. Phân tích hình ảnh
Nhận dạng và trích xuất từng câu hỏi với các thành phần:
### Thông tin bắt buộc:
- **Nội dung câu hỏi**: Toàn bộ văn bản câu hỏi (bao gồm cả đoạn đọc hiểu nếu có)
- **Các lựa chọn**: Tất cả đáp án (A, B, C, D, E...)
### Thông tin phân loại (Optional - chỉ khi có độ tin cậy ≥80%):
**Topic**: Chủ đề/lĩnh vực của câu hỏi (ví dụ: Toán học, Văn học, Lịch sử...)
**Bloom Level**:
- `remember`: Nhớ/ghi nhận thông tin (ví dụ: "Ai là...?", "Định nghĩa của... là gì?")
- `understand`: Giải thích/diễn đạt lại (ví dụ: "Tại sao...?", "Ý nghĩa của... là gì?")
- `apply`: Áp dụng vào tình huống (ví dụ: "Tính...", "Sử dụng công thức... để...")
- `analyze`: Phân tích/so sánh (ví dụ: "So sánh...", "Phân tích nguyên nhân...")
- `evaluate`: Đánh giá/phê phán (ví dụ: "Đánh giá...", "Quan điểm nào đúng nhất?")
- `create`: Tạo mới/tổng hợp (ví dụ: "Thiết kế...", "Đề xuất giải pháp...")
**Difficulty**:
- `easy`: Kiến thức trực tiếp, không cần suy luận phức tạp
- `medium`: Cần kết hợp 2-3 bước suy luận hoặc nhiều khái niệm
- `hard`: Phức tạp, cần tư duy phản biện hoặc tổng hợp nhiều kiến thức
### Lưu ý:
- **KHÔNG** trích xuất số thứ tự câu hỏi
- **KHÔNG** phân loại nếu không chắc chắn (để trống trường đó)
## 2. Xử lý đa ngôn ngữ: Tiếng Việt, Nhật, Anh

## 3. Nguyên tắc vàng
 **100% trung thành với nội dung gốc** - KHÔNG thêm, bớt, sửa, diễn giải
 Bảo toàn thứ tự câu hỏi và lựa chọn
 Giữ nguyên xuống dòng, khoảng trắng có ý nghĩa
 Nhận dạng chính xác công thức toán, ký hiệu khoa học
Ưu tiên độ chính xác > độ đầy đủ phân loại

# ĐỊNH DẠNG ĐẦU RA (OUTPUT FORMAT)
Sử dụng cấu trúc tags sau cho mỗi câu hỏi:
```
[Q_START]
[TEXT]
{Nội dung câu hỏi đầy đủ. Giữ nguyên xuống dòng.
Nếu là bài đọc hiểu, bao gồm toàn bộ đoạn văn trong phần này.}
[/TEXT]

[TOPIC]{Chủ đề câu hỏi - bỏ qua nếu không rõ}[/TOPIC]

[BLOOM]{remember|understand|apply|analyze|evaluate|create - bỏ qua nếu không chắc}[/BLOOM]

[DIFFICULTY]{easy|medium|hard - bỏ qua nếu không chắc}[/DIFFICULTY]

[OPTIONS]
A) {Nội dung lựa chọn A}
B) {Nội dung lựa chọn B}
C) {Nội dung lựa chọn C}
D) {Nội dung lựa chọn D}
[/OPTIONS]
[Q_END]
```
# CÁC QUY TẮC QUAN TRỌNG (CONSTRAINTS)
## Bỏ qua:
-  Ghi chú viết tay, dấu tích, gạch chéo
- Đánh dấu phía lề (✓, ✗, số điểm...)
- Số thứ tự câu hỏi (Question 1, Câu 2, 問3...)
- Watermark, logo, thông tin header/footer không liên quan

## Xử lý đặc biệt:
-  Nếu câu hỏi chứa hình ảnh/biểu đồ: ghi `[IMAGE_PLACEHOLDER]` tại vị trí đó
- Bảng biểu: mô tả cấu trúc hoặc dùng `[TABLE_PLACEHOLDER]`

## Nguyên tắc tối thượng:
 **TUYỆT ĐỐI KHÔNG** thêm, bớt, sửa, diễn giải, suy đoán nội dung
**TUYỆT ĐỐI KHÔNG** sửa lỗi chính tả có sẵn trong đề gốc
**TUYỆT ĐỐI KHÔNG** thay thế ký tự ngôn ngữ (VD: 東京 → Tokyo)
---
# BẮT ĐẦU PHÂN TÍCH

Hãy phân tích hình ảnh đề thi và trích xuất dữ liệu theo đúng format trên.

"""

FORMATTER_PROMPT_TEMPLATE = """
# VAI TRÒ
Công cụ chuyển đổi văn bản có gắn tag thành mảng JSON hợp lệ. Mục tiêu: MAXIMUM STRICTNESS — CHỈ trả về một mảng JSON, không có thêm chú thích, ký tự, hay fence Markdown.
---
# NHIỆM VỤ (tóm tắt)
1) Phân tích văn bản đầu vào văn bản đó chứa một hoặc nhiều block câu hỏi đã được gắn tag theo định dạng sau.
2) Trích xuất tuần tự từng câu hỏi theo thứ tự xuất hiện.
3) Trả về CHỈ một mảng JSON (một danh sách các object), hợp lệ theo schema bên dưới.
4) Chỉ ra đáp án đúng
---
# QUY ước TAGS (Input)
TAGS hợp lệ:
```
[Q_START]
[TEXT]...[/TEXT]
[TOPIC]...[/TOPIC]          (optional)
[BLOOM]...[/BLOOM]          (optional)
[DIFFICULTY]...[/DIFFICULTY] (optional)
[OPTIONS]
A) ...
B) ...
...
[/OPTIONS]
[Q_END]
```
QUY TẮC XỬ LÝ:
- Nếu tag [OPTIONS] bị thiếu → gán `options: []`.
- Nếu [IMAGE_PLACEHOLDER] xuất hiện trong text → `image_placeholder: true` và giữ nguyên token `[IMAGE_PLACEHOLDER]` trong `question_text`.
- Tag optional không tồn tại → gán `null`.
- Tag rỗng (ví dụ `[TOPIC][/TOPIC]`) → `null`.
- Nếu OCR có ký tự không đọc được (� hoặc chuỗi '???') → `is_readable: false`.
- Giữ nguyên xuống dòng và khoảng trắng có ý nghĩa bên trong `question_text` và `options.text` — *không* auto-trim nội dung nội bộ; chỉ loại bỏ khoảng trắng ở đầu/cuối khi cần để loại bỏ dấu thừa của OCR.
- Nhãn đáp án: chuẩn hoá chữ hoa Latin (A, B, C...) nếu có thể; nếu label không phải Latin (ví dụ: ①, 1.), lưu nguyên nhãn dưới trường `label` nhưng giữ thứ tự xuất hiện.
---
# LANGUAGE DETECTION
- `vi`: Tiếng Việt (có dấu thanh)
- `ja`: Tiếng Nhật (kanji/hiragana/katakana)
- `en`: Tiếng Anh
Xác định ngôn ngữ của toàn bộ `question_text`.
---

# OUTPUT SCHEMA (mỗi phần tử của mảng)
JSON trả về phải là một mảng, ví dụ:

```
[
    {{
        "language": "vi",
        "question_text": "Nội dung câu hỏi (giữ nguyên xuống dòng)",
        "topic": null,
        "bloom_level": null,
        "difficulty": null,
        "image_placeholder": false,
        "options": [
            {{ "label": "A", "text": "Đáp án A", "is_correct": false }},
            {{ "label": "B", "text": "Đáp án B",  "is_correct": true }}
        ],
        "is_readable": true
    }}
]
```

Ghi chú quan trọng:
- `topic`, `bloom_level`, `difficulty`: nếu không thể xác định hoặc tag không có → `null`.
- `options`: luôn là mảng; khi không có options thì `[]`.
- `image_placeholder`: boolean.
- `is_readable`: boolean.

---

# XỬ LÝ TRƯỜNG HỢP PHỨC TẠP / LỖI
- Nếu một câu hỏi có nhiều `[TEXT]` hoặc tag lồng nhau, ghép tất cả nội dung theo thứ tự xuất hiện trong `question_text`.
- Nếu nhãn option bị lặp (ví dụ hai 'A)'), giữ thứ tự xuất hiện và giữ nhãn như OCR đã cho, nhưng đặt một trường `label_conflict: true` *không bắt buộc* — tuy nhiên, KHÔNG thêm các trường ngoài schema chính.
- Nếu output không thể parse thành JSON hợp lệ → trả một JSON rỗng `[]` (thay vì text lỗi).
---
# NGUYÊN TẮC NGUYÊN VÕNG (PRINCIPLES)
- TUYỆT ĐỐI KHÔNG thêm, bớt, sửa, diễn giải, hoặc suy đoán nội dung gốc.
- Không sửa lỗi chính tả trong nội dung gốc.
- LOẠI BỎ SỐ THỨ TỰ CÂU HỎI
---
# NGAY LẬP TỨC (FORMATTER INPUT / OUTPUT)
OUTPUT: CHỈ một mảng JSON hợp lệ (không có fence markdown, không có chú thích text).

**Dữ liệu đầu vào (Input Data):**
{answer_text}

"""

# --- Gemini client & call helpers ---
def _init_gemini_client():
    if not GEMINI_API_KEY:
        raise RuntimeError("Missing GEMINI_API_KEY")
    return genai.Client(api_key=GEMINI_API_KEY)

def generate_answer(prompt: str, image_path: str | None = None) -> str:
    """
    Theo mẫu bạn dùng: from google import genai, Client, contents=[image, prompt]
    """
    try:
        client = _init_gemini_client()
        contents = [prompt]
        if image_path:
            img = Image.open(image_path)
            contents = [img, prompt]

        resp = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=contents,
        )

        if hasattr(resp, "text"):
            return resp.text
        if isinstance(resp, dict) and "text" in resp:
            return resp["text"]
        return "No answer generated."
    except Exception as e:
        return f"Error generating answer: {str(e)}"


# --- S3 / DDB helpers ---
def _s3_download_to_tmp(bucket: str, key: str) -> str:
    path = f"/tmp/{os.path.basename(key)}"
    os.makedirs("/tmp", exist_ok=True)
    S3.download_file(bucket, key, path)
    return path


def _ddb_put_document(table_name: str, pk: str, sk: str, items: list, meta: dict):
    """
    Lưu 1 item duy nhất: mỗi ảnh = 1 item.
    Lưu ý giới hạn 400KB/item của DynamoDB.
    """
    table = DDB.Table(table_name)
    item = {
        "PK": pk,
        "SK": sk,
        "created_at": datetime.now(tz=timezone.utc).isoformat(),
        "items_count": len(items),
        "items": items,
        "source_bucket": meta.get("bucket"),
        "source_key": meta.get("key"),
    }
    if meta.get("job_id"):
        item["job_id"] = meta["job_id"]

    table.put_item(Item=item)
    return item


# =========================================================
# 🧠 Lambda Handler (invoke từ Lambda A)
# =========================================================
def lambda_handler(event, context):
    """
    Dạng event khi được Lambda A gọi:
    {
        "bucket": "my-bucket",
        "key": "processed/example_warped.jpg",
        "job_id": "uuid-1234"
    }
    """
    try:
        bucket = event.get("bucket")
        key = event.get("key")
        job_id = event.get("job_id")  # có thể None nếu không truyền

        if not bucket or not key:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "Missing 'bucket' or 'key' in event"})
            }
        if not DDB_TABLE:
            return {
                "statusCode": 500,
                "body": json.dumps({"error": "Missing DDB_TABLE environment variable"})
            }

        # --- Tải ảnh ---
        img_path = _s3_download_to_tmp(bucket, key)

        # --- Bước 1: Gemini OCR ---
        extracted = generate_answer(SYSTEM_PROMPT, image_path=img_path)
        if not extracted or extracted.startswith("Error generating answer"):
            raise RuntimeError(f"OCR failed: {extracted}")

        # --- Bước 2: Format thành JSON ---
        formatter_prompt = FORMATTER_PROMPT_TEMPLATE.format(answer_text=extracted)
        formatted = generate_answer(formatter_prompt)

        raw = (formatted or "").strip()
        if raw.startswith("```json"):
            raw = raw.removeprefix("```json").removesuffix("```").strip()
        elif raw.startswith("```"):
            raw = raw.removeprefix("```").removesuffix("```").strip()

        data = json.loads(raw)
        if not isinstance(data, list):
            raise ValueError("Formatted result is not a JSON array")

        # --- Lưu DynamoDB ---
        base = os.path.splitext(os.path.basename(key))[0]
        pk = f"DOC#{base}"
        sk = "v1"

        saved = _ddb_put_document(
            table_name=DDB_TABLE,
            pk=pk,
            sk=sk,
            items=data,
            meta={"bucket": bucket, "key": key, "job_id": job_id}
        )

        # --- Response trả về ---
        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({
                "job_id": job_id,
                "ddb": {"table": DDB_TABLE, "pk": pk, "sk": sk},
                "items_count": saved["items_count"],
                "source": {"bucket": bucket, "key": key}
            }, ensure_ascii=False)
        }

    except Exception as e:
        print(f"[ERROR] {e}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }