import os
import json
import uuid
import boto3
import cv2
import numpy as np
import base64

# --- AWS Clients ---
s3 = boto3.client("s3")
lambda_client = boto3.client("lambda")

# ========= Các hàm xử lý ảnh =========

def order_points(pts):
    rect = np.zeros((4, 2), dtype="float32")
    pts = np.array(pts)
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]
    return rect

def four_point_transform(image, pts):
    rect = order_points(pts)
    (tl, tr, br, bl) = rect
    widthA = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
    widthB = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
    maxWidth = max(int(widthA), int(widthB))
    heightA = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
    heightB = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
    maxHeight = max(int(heightA), int(heightB))
    dst = np.array([
        [0, 0],
        [maxWidth - 1, 0],
        [maxWidth - 1, maxHeight - 1],
        [0, maxHeight - 1]
    ], dtype="float32")
    M = cv2.getPerspectiveTransform(rect, dst)
    return cv2.warpPerspective(image, M, (maxWidth, maxHeight))

def preprocess_image(image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    kernel = np.ones((5, 5), np.uint8)
    return cv2.morphologyEx(gray, cv2.MORPH_CLOSE, kernel, iterations=3)

def apply_grabcut(image_color, image_gray):
    if len(image_color.shape) != 3:
        return image_gray
    mask = np.zeros(image_color.shape[:2], np.uint8)
    bgd_model = np.zeros((1, 65), np.float64)
    fgd_model = np.zeros((1, 65), np.float64)
    rect = (20, 20, image_color.shape[1] - 40, image_color.shape[0] - 40)
    try:
        cv2.grabCut(image_color, mask, rect, bgd_model, fgd_model, 5, cv2.GC_INIT_WITH_RECT)
        mask2 = np.where((mask == 2) | (mask == 0), 0, 1).astype('uint8')
        return image_gray * mask2
    except Exception:
        return image_gray

def detect_edges(image):
    blurred = cv2.GaussianBlur(image, (11, 11), 0)
    v = np.median(blurred)
    lower = int(max(0, (1.0 - 0.33) * v))
    upper = int(min(255, (1.0 + 0.33) * v))
    edged = cv2.Canny(blurred, lower, upper)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    return cv2.dilate(edged, kernel)

def find_document_contour(edged):
    contours, _ = cv2.findContours(edged, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    contours = sorted(contours, key=cv2.contourArea, reverse=True)
    for contour in contours:
        peri = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, 0.02 * peri, True)
        if len(approx) == 4 and cv2.contourArea(approx) > 1000:
            return approx
    return None

def cv2_imdecode_from_bytes(b: bytes):
    arr = np.frombuffer(b, dtype=np.uint8)
    return cv2.imdecode(arr, cv2.IMREAD_COLOR)

def cv2_imencode_to_jpg_bytes(img, quality=90):
    ok, buf = cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    if not ok:
        raise RuntimeError("Failed to encode image to JPEG")
    return buf.tobytes()

def process_np_image(image_np, use_grabcut=True, resize_limit=1080):
    if image_np is None:
        return None
    orig = image_np.copy()
    max_dim = max(image_np.shape[:2])
    if max_dim > resize_limit:
        scale_factor = resize_limit / max_dim
        image_np = cv2.resize(image_np, None, fx=scale_factor, fy=scale_factor)
    else:
        scale_factor = 1.0

    processed = preprocess_image(image_np)
    if use_grabcut:
        processed = apply_grabcut(image_np, processed)
    edged = detect_edges(processed)
    document_contour = find_document_contour(edged)
    if document_contour is None:
        return None
    if scale_factor != 1.0:
        document_contour = document_contour / scale_factor
    pts = document_contour.reshape(4, 2)
    warped = four_point_transform(orig, pts)
    return warped


# ========= Lambda Handler (chuẩn chỉnh) =========
def handler(event, context):
    print("=== RAW EVENT ===")
    print(str(event)[:1000])  # log event để debug

    # ✅ Parse khi nhận từ API Gateway hoặc Lambda URL
    if isinstance(event, dict) and "body" in event:
        try:
            body = event["body"]
            if isinstance(body, str):
                event = json.loads(body)
            elif isinstance(body, (bytes, bytearray)):
                event = json.loads(body.decode("utf-8"))
        except Exception as e:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": f"Invalid JSON body: {e}"})
            }

    OUTPUT_BUCKET = os.getenv("OUTPUT_BUCKET")
    OUTPUT_PREFIX = os.getenv("OUTPUT_PREFIX", "processed/")
    OCR_FUNCTION = os.getenv("OCR_FUNCTION_NAME")

    image_b64 = event.get("image_base64")
    filename = event.get("filename", "uploaded.jpg")
    job_id = event.get("job_id") or str(uuid.uuid4())

    if not image_b64:
        return {"statusCode": 400, "body": json.dumps({"error": "Missing field: image_base64"})}
    if not OUTPUT_BUCKET:
        return {"statusCode": 500, "body": json.dumps({"error": "Missing env: OUTPUT_BUCKET"})}

    # --- Decode ảnh ---
    try:
        img_bytes = base64.b64decode(image_b64)
        image = cv2_imdecode_from_bytes(img_bytes)
    except Exception as e:
        return {"statusCode": 400, "body": json.dumps({"error": f"Failed to decode image: {e}"})}

    if image is None:
        return {"statusCode": 422, "body": json.dumps({"error": "Invalid image data"})}

    # --- Xử lý ảnh ---
    warped = process_np_image(image)
    if warped is None:
        return {"statusCode": 422, "body": json.dumps({"error": "No document contour found"})}

    # --- Upload ảnh đã xử lý lên S3 ---
    try:
        out_jpg = cv2_imencode_to_jpg_bytes(warped, quality=92)
        out_key = f"{OUTPUT_PREFIX}{os.path.splitext(filename)[0]}_warped.jpg"
        s3.put_object(
            Bucket=OUTPUT_BUCKET,
            Key=out_key,
            Body=out_jpg,
            ContentType="image/jpeg"
        )
        print(f"[Lambda A] ✅ Saved processed image to s3://{OUTPUT_BUCKET}/{out_key}")
    except Exception as e:
        return {"statusCode": 500, "body": json.dumps({"error": f"Failed to upload processed image: {e}"})}

    # --- Invoke Lambda B (OCR Lambda) ---
    if OCR_FUNCTION:
        payload = {
            "bucket": OUTPUT_BUCKET,
            "key": out_key,
            "source": "lambda_img_process",
            "job_id": job_id
        }
        try:
            lambda_client.invoke(
                FunctionName=OCR_FUNCTION,
                InvocationType="Event",
                Payload=json.dumps(payload).encode("utf-8")
            )
            print(f"[Lambda A] 🚀 Invoked OCR Lambda: {OCR_FUNCTION} (job_id={job_id})")
        except Exception as e:
            print(f"[Lambda A] ⚠️ Failed to invoke OCR Lambda: {e}")

    # --- Trả phản hồi ---
    s3_url = f"s3://{OUTPUT_BUCKET}/{out_key}"
    return {
        "statusCode": 200,
        "body": json.dumps({
            "status": "ok",
            "job_id": job_id,
            "processed_image": s3_url,
            "message": "Image processed successfully, OCR is running asynchronously."
        })
    }
