from pathlib import Path
import requests
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi.responses import FileResponse

from backend.PaperManager import ResearchPaper, AIInsight

UPLOAD_DIR = Path("uploads")
URL = "https://pseudoetymological-gretchen-overproof.ngrok-free.dev/"

async def get_paper_or_404(
    paper_id: int,
    user_id: int,
    db: AsyncSession
) -> ResearchPaper:
    result = await db.execute(
        select(ResearchPaper)
        .where(
            ResearchPaper.id == paper_id,
            ResearchPaper.user_id == user_id
        )
    )
    paper = result.scalars().first()

    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    return paper


async def get_file_from_paper(paper: ResearchPaper)->FileResponse:
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


async def call_ai_api(*args):

    return "hi" #requests.post(URL+"/process-research")


async def process_ai(paper_id: int):
    print("Background task started for:", paper_id)

    from backend.database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:

        try:
            paper = await db.get(ResearchPaper, paper_id)
            print("Loaded paper:", paper)

            if not paper:
                print("Paper not found")
                return

            if paper.file_type == "pdf":
                file_path = UPLOAD_DIR / paper.file_path
                print("Reading file:", file_path)

                with open(file_path, "rb") as f:
                    ai_response = await call_ai_api(f.read())

            elif paper.file_type == "editor_json":
                ai_response = await call_ai_api(paper.content_json)

            else:
                print("Unsupported file type")
                paper.analysis_status = "failed"
                await db.commit()
                return

            print("AI Response received")

            insight = AIInsight(
                paper_id=paper.id,
                summary=ai_response
            )

            db.add(insight)
            paper.analysis_status = "completed"

            await db.commit()

            print("Status updated to completed")

        except Exception as e:
            print("ERROR IN BACKGROUND:", e)
            paper.analysis_status = "failed"
            await db.commit()


async def call_chatbot_api(*args, **kwargs):
    return "hi"
