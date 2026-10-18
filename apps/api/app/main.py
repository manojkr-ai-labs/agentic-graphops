"""HTTP app. Health, investigations, and the one approve route."""

from __future__ import annotations

import uuid
from typing import Literal

import uvicorn
from fastapi import FastAPI, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, ValidationError

from app.api.investigations import InvestigationService
from app.config import Settings, configuration_error, load_settings
from app.graph.client import GraphGateway, ToolFailure
from app.obs.log import configure_logging, log_step


class HealthBody(BaseModel):
    status: Literal["healthy", "unhealthy"]
    api: Literal["up"]
    graph: Literal["up", "down"]


class InvestigationRequest(BaseModel):
    sessionId: str
    question: str = Field(min_length=1, max_length=2000)


class ApproveRequest(BaseModel):
    approvalToken: str | None = None


def create_app(settings: Settings | None = None) -> FastAPI:
    try:
        cfg = settings if settings is not None else load_settings()
    except ValidationError as exc:
        raise SystemExit(configuration_error(exc)) from None

    logger = configure_logging(cfg.log_level)
    gateway = GraphGateway(cfg)
    service = InvestigationService(cfg, gateway, logger)
    app = FastAPI(title="GraphOps")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )
    app.state.service = service

    @app.get("/api/health", response_model=HealthBody)
    def health() -> JSONResponse:
        request_id = str(uuid.uuid4())
        outcome = gateway.ping()
        if isinstance(outcome, ToolFailure):
            log_step(
                logger,
                requestId=request_id,
                step="health",
                durationMs=outcome.duration_ms,
                resultCount=0,
                status="unhealthy",
                errorCategory=outcome.error_category,
            )
            body = HealthBody(status="unhealthy", api="up", graph="down")
            return JSONResponse(status_code=503, content=body.model_dump())

        log_step(
            logger,
            requestId=request_id,
            step="health",
            durationMs=outcome.duration_ms,
            resultCount=outcome.result_count,
            status="healthy",
        )
        body = HealthBody(status="healthy", api="up", graph="up")
        return JSONResponse(status_code=200, content=body.model_dump())

    @app.post("/api/investigations")
    def start_investigation(
        payload: InvestigationRequest,
        x_tenant_id: str = Header(default=""),
        x_actor: str = Header(default=""),
    ) -> JSONResponse:
        request_id = str(uuid.uuid4())
        body = service.start(
            tenant=x_tenant_id,
            actor=x_actor,
            session_id=payload.sessionId,
            question=payload.question,
            request_id=request_id,
        )
        status_code = 200
        if body["status"] in {"TOOL FAILURE", "SYSTEM ERROR"}:
            status_code = 503
        return JSONResponse(status_code=status_code, content=body)

    @app.get("/api/investigations/{investigation_id}")
    def read_investigation(investigation_id: str) -> JSONResponse:
        body = service.get(investigation_id)
        if body is None:
            return JSONResponse(status_code=404, content={"status": "NO EVIDENCE"})
        return JSONResponse(status_code=200, content=body)

    @app.post("/api/investigations/{investigation_id}/approve")
    def approve_investigation(
        investigation_id: str,
        payload: ApproveRequest,
        x_actor: str = Header(default=""),
    ) -> JSONResponse:
        request_id = str(uuid.uuid4())
        body = service.approve(investigation_id, payload.approvalToken, x_actor, request_id)
        if body is None:
            return JSONResponse(status_code=404, content={"status": "NO EVIDENCE"})
        return JSONResponse(status_code=200, content=body)

    return app


def main() -> None:
    uvicorn.run(create_app, factory=True, host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
