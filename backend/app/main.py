from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import auth, images, flavors, libraries, instances, admin

app = FastAPI(
    title="Union",
    description="OpenStack VM 배포 + OverlayFS 마운트 웹 플랫폼",
    version="0.1.0",
)

# CORS: credentials 사용 시 allow_origins=["*"] 는 브라우저가 거부하므로
# 요청 Origin을 동적으로 허용 (개발 환경)
@app.middleware("http")
async def cors_middleware(request: Request, call_next):
    origin = request.headers.get("origin", "")
    response = await call_next(request)
    if origin:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS, PATCH"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-Auth-Token, X-Project-Id, Authorization"
        response.headers["Vary"] = "Origin"
    return response


@app.options("/{rest_of_path:path}")
async def options_handler(request: Request, rest_of_path: str):
    """OPTIONS preflight 전용 핸들러."""
    origin = request.headers.get("origin", "*")
    return JSONResponse(
        content="OK",
        headers={
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS, PATCH",
            "Access-Control-Allow-Headers": "Content-Type, X-Auth-Token, X-Project-Id, Authorization",
            "Access-Control-Max-Age": "600",
            "Vary": "Origin",
        },
    )


app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(images.router, prefix="/api/images", tags=["images"])
app.include_router(flavors.router, prefix="/api/flavors", tags=["flavors"])
app.include_router(libraries.router, prefix="/api/libraries", tags=["libraries"])
app.include_router(instances.router, prefix="/api/instances", tags=["instances"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])


@app.get("/api/health")
async def health():
    return {"status": "ok"}
