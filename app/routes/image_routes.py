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

dynamodb = boto3.client('dynamodb', region_name='ap-northeast-1')
RESULTS_TABLE = dynamodb.Table('std-dacn-questions-table-truonggiahuy')

@image_bp.route("/result/<string:job_id>", methods=["GET"])
@jwt_required(optional=True)
def get_result(job_id):
    """Lấy kết quả xử lý ảnh từ DynamoDB bằng boto3.client"""
    try:
        client = boto3.client("dynamodb", region_name="ap-northeast-1")
        resp = client.get_item(
            TableName=RESULTS_TABLE,
            Key={"job_id": {"S": job_id}}
        )

        if "Item" not in resp:
            return jsonify({
                "message": f"Không tìm thấy kết quả cho job_id: {job_id}"
            }), 404

        # ✅ Dùng TypeDeserializer để chuyển đổi
        deserializer = TypeDeserializer()

        def convert(item):
            return {k: deserializer.deserialize(v) for k, v in item.items()}

        clean_item = convert(resp["Item"])

        return jsonify({
            "message": "Truy vấn thành công",
            "data": clean_item
        }), 200

    except Exception as e:
        current_app.logger.error(f"Lỗi DynamoDB: {str(e)}")
        return jsonify({
            "message": "Lỗi không xác định",
            "error": str(e)
        }), 500
    """Lấy kết quả xử lý ảnh theo job_id từ DynamoDB (convert bằng TypeDeserializer)"""
    try:
        table = dynamodb.Table(RESULTS_TABLE)
        response = table.get_item(Key={"job_id": job_id})
        raw_item = response.get("Item")

        if not raw_item:
            return jsonify({
                "message": f"Không tìm thấy kết quả cho job_id: {job_id}"
            }), 404

        # ✅ Sử dụng AWS TypeDeserializer để convert tất cả field
        deserializer = TypeDeserializer()

        def dynamo_to_python(value):
            """Convert AttributeValue -> Python object an toàn"""
            # Dữ liệu boto3 trả về có dạng {"S": "..."} | {"M": {...}} | ...
            if isinstance(value, dict) and len(value) == 1 and list(value.keys())[0] in ["S", "N", "BOOL", "NULL", "M", "L"]:
                return deserializer.deserialize(value)
            elif isinstance(value, dict):
                return {k: dynamo_to_python(v) for k, v in value.items()}
            elif isinstance(value, list):
                return [dynamo_to_python(v) for v in value]
            else:
                return value

        clean_item = dynamo_to_python(raw_item)

        return jsonify({
            "message": "Truy vấn thành công",
            "data": clean_item
        }), 200

    except Exception as e:
        current_app.logger.error(f"Unexpected error: {str(e)}")
        return jsonify({
            "message": "Lỗi không xác định",
            "error": str(e)
        }), 500
    """Lấy kết quả xử lý ảnh theo job_id từ DynamoDB (đã convert về JSON chuẩn)"""
    try:
        table = dynamodb.Table(RESULTS_TABLE)
        response = table.get_item(Key={"job_id": job_id})
        item = response.get("Item")

        if not item:
            return jsonify({
                "message": f"Không tìm thấy kết quả cho job_id: {job_id}"
            }), 404

        # ✅ Chuyển từ AttributeValue sang dict thuần
        deserializer = TypeDeserializer()

        def deserialize(data):
            """Chuyển mọi field từ DynamoDB AttributeValue sang JSON chuẩn"""
            if isinstance(data, dict):
                if set(data.keys()) == {"S"}:
                    return data["S"]
                if set(data.keys()) == {"N"}:
                    return float(data["N"]) if "." in data["N"] else int(data["N"])
                if set(data.keys()) == {"BOOL"}:
                    return data["BOOL"]
                if set(data.keys()) == {"L"}:
                    return [deserialize(i) for i in data["L"]]
                if set(data.keys()) == {"M"}:
                    return {k: deserialize(v) for k, v in data["M"].items()}
                # fallback nếu dict không theo format DynamoDB
                return {k: deserialize(v) for k, v in data.items()}
            elif isinstance(data, list):
                return [deserialize(i) for i in data]
            else:
                return data

        clean_item = deserialize(item)

        return jsonify({
            "message": "Truy vấn thành công",
            "data": clean_item
        }), 200

    except ClientError as e:
        current_app.logger.error(f"DynamoDB error: {e.response['Error']['Message']}")
        return jsonify({
            "message": "Lỗi truy vấn DynamoDB",
            "error": e.response['Error']['Message']
        }), 500
    except Exception as e:
        current_app.logger.error(f"Unexpected error: {str(e)}")
        return jsonify({
            "message": "Lỗi không xác định",
            "error": str(e)
        }), 500