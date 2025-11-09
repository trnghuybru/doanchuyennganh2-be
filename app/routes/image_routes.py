import base64
import uuid
import json
import requests
from flask import Blueprint, request, jsonify, current_app
from datetime import datetime
from flask_jwt_extended import jwt_required, get_jwt_identity
from config import Config
import boto3
from botocore.exceptions import ClientError
from boto3.dynamodb.types import TypeDeserializer

image_bp = Blueprint("image", __name__)

@image_bp.route("/upload", methods=["POST"])
@jwt_required()
def upload_image():
    """API Upload ảnh → Gửi đến Lambda A xử lý → Nhận lại job_id"""

    user_id = get_jwt_identity()
    if not user_id:
        return jsonify({"message": "Unauthorized"}), 401

    if "file" not in request.files:
        return jsonify({"message": "No file uploaded"}), 400

    file = request.files["file"]
    image_bytes = file.read()
    if not image_bytes:
        return jsonify({"message": "Uploaded file is empty"}), 400

    filename = file.filename or f"upload_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.jpg"
    job_id = str(uuid.uuid4())

    # ✅ Payload gửi tới Lambda (JSON phẳng)
    payload = {
        "image_base64": base64.b64encode(image_bytes).decode("utf-8"),
        "filename": filename,
        "job_id": job_id,
        "user_id": user_id
    }

    try:
        current_app.logger.info(f"📤 Sending image to Lambda A: {Config.LAMBDA_IMG_ENDPOINT}")

        resp = requests.post(
            Config.LAMBDA_IMG_ENDPOINT,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=60
        )

        current_app.logger.info(f"📥 Lambda responded with status {resp.status_code}")

        # Nếu Lambda lỗi
        if resp.status_code != 200:
            return jsonify({
                "message": "Failed to process image",
                "lambda_response": resp.text
            }), resp.status_code

        # ✅ Parse phản hồi JSON
        try:
            result = resp.json()
        except Exception:
            return jsonify({
                "message": "Invalid response from Lambda",
                "raw_response": resp.text
            }), 500

        # Lambda chuẩn sẽ trả {"statusCode":200, "body":"{...}"}
        body = result.get("body", result)
        if isinstance(body, str):
            try:
                body = json.loads(body)
            except Exception:
                body = {"raw_body": body}

        return jsonify({
            "message": "Image uploaded successfully",
            "job_id": body.get("job_id", job_id),
            "processed_image": body.get("processed_image"),
            "lambda_message": body.get("message", "No message from Lambda")
        }), 202

    except requests.exceptions.RequestException as e:
        current_app.logger.error(f"❌ Lambda request error: {e}")
        return jsonify({
            "message": "Failed to connect to Lambda A",
            "error": str(e)
        }), 502

    except Exception as e:
        current_app.logger.error(f"❌ Unexpected error: {e}")
        return jsonify({
            "message": "Error invoking Lambda A",
            "error": str(e)
        }), 500

LAMBDA_API_BASE = "https://006w081cdi.execute-api.ap-northeast-1.amazonaws.com" 

RESULTS_TABLE = "std-dacn-questions-table-truonggiahuy"

@image_bp.route("/result/<string:job_id>", methods=["GET"])
@jwt_required(optional=True)
def get_result(job_id):
    """Gọi Lambda API (path parameters) để lấy kết quả xử lý ảnh từ DynamoDB"""
    try:
        # ✅ Gọi đúng format path-based route của API Gateway
        url = f"{LAMBDA_API_BASE}/dynamodb/{RESULTS_TABLE}/{job_id}"
        current_app.logger.info(f"Đang gọi Lambda API: {url}")

        resp = requests.get(url, timeout=15)

        if resp.status_code != 200:
            current_app.logger.error(f"Lỗi Lambda: {resp.status_code} - {resp.text}")
            return jsonify({
                "message": f"Lỗi khi gọi Lambda (HTTP {resp.status_code})",
                "error": resp.text
            }), resp.status_code

        data = resp.json()

        return jsonify({
            "message": "Truy vấn thành công",
            "data": data.get("data")
        }), 200

    except requests.exceptions.RequestException as e:
        current_app.logger.error(f"Lỗi kết nối Lambda API: {str(e)}")
        return jsonify({
            "message": "Không thể kết nối Lambda API",
            "error": str(e)
        }), 502

    except Exception as e:
        current_app.logger.error(f"Lỗi không xác định: {str(e)}")
        return jsonify({
            "message": "Lỗi không xác định",
            "error": str(e)
        }), 500