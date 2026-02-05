"""FastAPI 앱 진입점"""

import os
import sys

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from crawler_logging import CrawlerLogger

# 로깅 설정 (콘솔 출력, OpenObserve 비활성화)
CrawlerLogger.configure(
    level=os.environ.get("LOG_LEVEL", "DEBUG"),
    console=True,
    openobserve=False,
)

app = FastAPI(
    title="Book Crawler API",
    description="여러 플랫폼의 책 평점을 수집하는 API",
    version="0.1.0",
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://*.vercel.app",
    ],
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 등록
from api.routes.search import router as search_router

app.include_router(search_router, prefix="/api")


@app.get("/")
async def root():
    return {"status": "ok", "service": "book-crawler-api"}


@app.get("/health")
async def health():
    return {"status": "healthy"}
