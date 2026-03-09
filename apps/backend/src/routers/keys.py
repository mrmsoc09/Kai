from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from apps.backend.src.core.key_manager import key_manager
from apps.backend.src.core.auth import require_roles

router = APIRouter(prefix="/keys", tags=["keys"])

@router.post("/import", dependencies=[Depends(require_roles(["admin"]))])
async def import_keys(file: UploadFile = File(...)):
    """
    Bulk import API keys from CSV or PDF.
    Requires admin privileges.
    """
    try:
        result = await key_manager.process_key_file(file)
        return result
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
