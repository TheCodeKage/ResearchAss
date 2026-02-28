from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.PaperManager import ResearchPaper, AIInsight

UPLOAD_DIR = Path("uploads")

async def call_ai_api(*args, **kwargs):
    return "hi"

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