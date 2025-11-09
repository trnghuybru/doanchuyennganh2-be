FROM public.ecr.aws/lambda/python:3.12

RUN python -m pip install --no-cache-dir \
    boto3==1.34.162 \
    Pillow==11.3.0 \
    google-genai>=0.3.0 \
    requests==2.32.3

COPY lambda_ocr.py ${LAMBDA_TASK_ROOT}

CMD ["lambda_ocr.lambda_handler"]
