import json

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from sqlalchemy import select, exists
from sqlalchemy.ext.asyncio import AsyncSession
import uuid
from pathlib import Path

from .models import ResearchPaper, AIInsight, ChatMessage
from backend.database import get_db
from .util import process_ai, call_chatbot_api
from .schemas import ChatRequest

from backend.Auth import User, get_current_user

router = APIRouter()

UPLOAD_DIR = Path("uploads")


@router.post("/upload")
async def upload_paper(
        file: UploadFile = File(...),
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):

    UPLOAD_DIR.mkdir(exist_ok=True)
    content = await file.read()
    print("Content type:", file.content_type)

    # -------------------
    # CASE 1: PDF
    # -------------------

    if file.filename.endswith(".pdf"):

        # Validate PDF header
        if not content.startswith(b"%PDF"):
            raise HTTPException(status_code=400, detail="Invalid PDF file")

        unique_filename = f"{uuid.uuid4()}.pdf"
        file_path = UPLOAD_DIR / unique_filename

        with open(file_path, "wb") as f:
            f.write(content)

        paper = ResearchPaper(
            filename=file.filename,
            file_path=unique_filename,
            content_json=None,
            file_type="pdf",
            user_id=current_user.id,
        )

    # -------------------
    # CASE 2: JSON
    # -------------------

    elif file.filename.endswith(".json"):

        try:
            json_data = json.loads(content)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid JSON file")

        paper = ResearchPaper(
            filename=file.filename,
            file_path=None,
            content_json=json_data,
            file_type="editor_json",
            user_id = current_user.id,
        )

    else:
        raise HTTPException(
            status_code=400,
            detail="Only PDF or JSON files are allowed"
        )

    db.add(paper)
    await db.commit()
    await db.refresh(paper)

    return {"id": paper.id}

@router.post("/{paper_id}/analyze")
async def analyze_paper(
        paper_id: int,
        background_tasks: BackgroundTasks,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):

    result = await db.execute(
        select(ResearchPaper)
        .where(
            ResearchPaper.id == paper_id,
            ResearchPaper.user_id == current_user.id
        )
    )
    paper = result.scalars().first()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    if paper.analysis_status == "processing":
        return {"message": "Already processing"}

    if paper.analysis_status == "completed":
        return {"message": "Already analyzed", "insight_url": f"/{paper_id}/insights"}

    paper.analysis_status = "processing"
    await db.commit()

    background_tasks.add_task(process_ai, paper_id)
    print("Background task started for:", paper_id)

    return {"message": "Analysis started"}


@router.get("/{paper_id}/insights")
async def get_insights(
        paper_id: int,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user)
):

    result = await db.execute(
        select(AIInsight).where(AIInsight.paper_id == paper_id and AIInsight.paper.user_id == current_user.id)
    )
    insights = result.scalars().all()

    return [insight.summary for insight in insights]


@router.get("/{paper_id}")
async def view_paper(
        paper_id: int,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user)
):

    result = await db.execute(
        select(ResearchPaper)
        .where(
            ResearchPaper.id == paper_id,
            ResearchPaper.user_id == current_user.id
        )
    )
    paper = result.scalars().first()

    # -------------------
    # CASE 1: PDF
    # -------------------

    if paper.file_type == "pdf":

        file_path = UPLOAD_DIR / paper.file_path

        if not file_path.exists():
            raise HTTPException(status_code=404, detail="File not found on disk")

        return FileResponse(
            path=file_path,
            media_type="application/pdf",
            filename=paper.filename
        )

    # -------------------
    # CASE 2: Editor JSON
    # -------------------

    elif paper.file_type == "editor_json":
        return paper.content_json

    else:
        raise HTTPException(status_code=400, detail="Unsupported file type")


@router.get("")
async def list_papers(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):

    result = await db.execute(select(ResearchPaper).where(ResearchPaper.user_id == current_user.id))
    papers = result.scalars().all()

    response = []

    for paper in papers:
        has_insight = await db.scalar(
            select(exists().where(AIInsight.paper_id == paper.id))
        )

        response.append({
            "id": paper.id,
            "filename": paper.filename,
            "file_type": paper.file_type,
            "uploaded_at": paper.uploaded_at,
            "has_insights": has_insight
        })

    return response

@router.post("/{paper_id}/chatbot/")
async def chatbot(
        paper_id: int,
        request: ChatRequest,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user)
):

    result = await db.execute(
        select(ResearchPaper)
        .where(
            ResearchPaper.id == paper_id,
            ResearchPaper.user_id == current_user.id
        )
    )
    paper = result.scalars().first()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    user_message = ChatMessage(
        paper_id=paper_id,
        role="user",
        content=request.message
    )
    db.add(request.message)
    await db.commit()

    ai_reply = await call_chatbot_api(user_message)
    assistant_message = ChatMessage(
        paper_id=paper_id,
        role="assistant",
        content=ai_reply
    )
    db.add(assistant_message)
    await db.commit()

    return {"response": ai_reply}


@router.get("/{paper_id}/chatbot/")
async def chat_history(
        paper_id: int,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user)
):

    result = await db.execute(
        select(ResearchPaper)
        .where(
            ResearchPaper.id == paper_id,
            ResearchPaper.user_id == current_user.id
        )
    )
    paper = result.scalars().first()

    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.paper_id == paper_id and ChatMessage.paper.user_id == current_user.id)
        .order_by(ChatMessage.created_at)
    )
    messages = result.scalars().all()

    return [
        {
            "role": msg.role,
            "content": msg.content,
            "created_at": msg.created_at
        }
        for msg in messages
    ]
