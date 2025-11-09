FROM public.ecr.aws/lambda/python:3.12
RUN python -m pip install --no-cache-dir \
    numpy==1.26.4 \
    opencv-python-headless==4.10.0.84 \
    boto3==1.34.162
COPY lambda_img_process.py ${LAMBDA_TASK_ROOT}
CMD ["lambda_img_process.handler"]