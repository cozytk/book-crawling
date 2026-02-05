FROM python:3.11-slim

WORKDIR /app

# 의존성 설치
COPY api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 소스 코드 복사
COPY crawlers/ ./crawlers/
COPY models/ ./models/
COPY crawler_logging/ ./crawler_logging/
COPY api/ ./api/

ENV PORT=8000
EXPOSE 8000

CMD sh -c "uvicorn api.app:app --host 0.0.0.0 --port $PORT"
