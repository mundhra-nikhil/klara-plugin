from fastapi import APIRouter, HTTPException, Depends
from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from src.repositories.db_setup import get_db
from src.services.sharepoint_service import sharepoint_service

router = APIRouter()

@router.get("/sites/{site_id}/files")
async def list_sharepoint_files(site_id: str, db: AsyncSession = Depends(get_db)) -> List[Dict[str, Any]]:
    """List Word documents from a specific SharePoint site."""
    try:
        files = await sharepoint_service.list_files(db, site_id)
        return files
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Server Error: {repr(e)}")

@router.get("/sites/{site_id}/files/{file_id}/download")
async def download_sharepoint_file(site_id: str, file_id: str, db: AsyncSession = Depends(get_db)):
    """Download a specific file from SharePoint (used by internal pipelines or debugging)."""
    try:
        content = await sharepoint_service.download_file(db, site_id, file_id)
        # Return as a response with appropriate headers
        from fastapi.responses import Response
        return Response(content=content, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
