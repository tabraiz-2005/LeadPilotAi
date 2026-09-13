"""Portfolio upload, parsing, persistence, and RAG ingestion routes."""

from pathlib import Path
from uuid import uuid4
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import PortfolioItem
from app.schemas import PortfolioItemOut, PortfolioUploadResult
from app.services.portfolio_parser import parse_file
from app.services.rag_service import ingest_portfolio_item

router = APIRouter()
UPLOAD_DIR = Path("data/portfolio_uploads")
ALLOWED_SUFFIXES = {".pdf", ".docx", ".txt"}


@router.post("/upload", response_model=PortfolioUploadResult)
def upload_portfolio_items(files: list[UploadFile] = File(...), db: Session = Depends(get_db)):
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    created = []
    for uploaded in files:
        suffix = Path(uploaded.filename or "").suffix.lower()
        if suffix not in ALLOWED_SUFFIXES:
            raise HTTPException(status_code=400, detail=f"Unsupported file type: {suffix}")
        safe_path = UPLOAD_DIR / f"{uuid4().hex}{suffix}"
        safe_path.write_bytes(uploaded.file.read())
        try:
            content = parse_file(str(safe_path))
        except Exception as exc:
            safe_path.unlink(missing_ok=True)
            raise HTTPException(status_code=400, detail=f"Could not parse {uploaded.filename}: {exc}")
        if not content.strip():
            safe_path.unlink(missing_ok=True)
            raise HTTPException(status_code=400, detail=f"No readable text found in {uploaded.filename}")
        item = PortfolioItem(title=uploaded.filename, content=content, file_name=uploaded.filename)
        db.add(item)
        db.flush()
        ingest_portfolio_item(str(item.id), [str(safe_path)])
        created.append(item)
    db.commit()
    for item in created:
        db.refresh(item)
    return {"ingested_count": len(created), "items": created}


@router.get("/", response_model=list[PortfolioItemOut])
def list_portfolio_items(db: Session = Depends(get_db)):
    return db.query(PortfolioItem).order_by(PortfolioItem.created_at.desc()).all()
