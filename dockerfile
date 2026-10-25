# Stage 1: Build
FROM python:3.12-slim AS builder

WORKDIR /build

COPY requirements.txt .

# Cài dependencies vào /install để copy sang stage 2
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# Stage 2: Production
FROM python:3.12-slim

WORKDIR /app

# Copy dependencies từ /install ở stage build sang /usr/local
# /usr/local là nơi Python có thể tìm thấy các package như Flask, Gunicorn...
COPY --from=builder /install /usr/local

# Cập nhật metadata package -> nâng cấp các package hệ điều hành -> xóa metadata APT để giảm dung lượng image
RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*

# Copy source code
COPY . .

# Tạo user riêng, không chạy app bằng root (least-privilege)
RUN useradd --create-home appuser \
    && chown -R appuser:appuser /app

# Chạy container bằng user thường
USER appuser

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:create_app()"]