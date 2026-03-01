import asyncio
from pathlib import Path
import requests
import json
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

    with open("backend/PaperManager/temp.json", "r") as f:
        return json.load(f)


# util.py
async def process_ai(paper_id: int):
    print("Background task started for:", paper_id)

    from backend.database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        try:
            # 1. Fetch the paper
            paper = await db.get(ResearchPaper, paper_id)
            if not paper:
                print(f"Paper {paper_id} not found")
                return

            # 2. Get AI Response
            if paper.file_type == "pdf":
                file_path = UPLOAD_DIR / paper.file_path
                with open(file_path, "rb") as f:
                    ai_response = await call_ai_api(f.read())
            elif paper.file_type == "editor_json":
                ai_response = await call_ai_api(paper.content_json)
            else:
                paper.analysis_status = "failed"
                await db.commit()
                return

            print("AI Response received")

            # 3. Create and add the insight
            insight = AIInsight(
                paper_id=paper.id,
                summary=ai_response  # Ensure this is a dict or list, not a string
            )
            db.add(insight)

            # 4. Update paper status
            paper.analysis_status = "completed"

            # 5. Commit all changes
            await db.commit()
            print("Status updated to completed and insight saved.")

        except Exception as e:
            print("ERROR IN BACKGROUND:", e)
            await db.rollback()  # Rollback to prevent partial data saving

            # Re-fetch paper to update status
            paper = await db.get(ResearchPaper, paper_id)
            if paper:
                paper.analysis_status = "failed"
                await db.commit()


async def call_chatbot_api(*args, **kwargs):
    return "hi"


if __name__ == "__main__":
    async def debug_ai_call():
        # Await the coroutine to get the actual result
        result = await call_ai_api()

        print("--- AI API RESULT ---")
        print(result)
        print(type(result))  # Verify it's a dict or list, not a string
        print("---------------------")


    # Run the debug function
    asyncio.run(debug_ai_call())