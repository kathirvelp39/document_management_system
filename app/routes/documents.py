
import uuid
from pathlib import Path

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Document, DocumentShare, User
from app.permissions import require_roles
from app.routes.auth import get_current_user

router = APIRouter(prefix="/documents", tags=["Documents"])

UPLOAD_DIR = Path(__file__).resolve().parents[2] / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

MAX_FILE_SIZE = 5 * 1024 * 1024
MAX_FILES_PER_REQUEST = 10

ALLOWED_TYPES = {
    ".pdf": {"application/pdf"},
    ".txt": {"text/plain"},
    ".png": {"image/png"},
    ".jpg": {"image/jpeg"},
    ".jpeg": {"image/jpeg"},
}

PERMISSION_LEVELS = {
    "view": 1,
    "download": 2,
    "edit": 3,
}


def document_response(document: Document) -> dict:
    return {
        "id": document.id,
        "filename": document.filename,
        "content_type": document.content_type,
        "file_size": document.file_size,
        "owner_id": document.owner_id,
        "created_at": document.created_at,
    }


def get_accessible_document(
    document_id: int,
    user: User,
    db: Session,
    required_permission: str = "view",
) -> Document:
    """Check document ownership, admin access, and sharing permission."""
    document = db.get(Document, document_id)

    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    # Owners have full access to their documents.
    if document.owner_id == user.id:
        return document

    # Admins can access all documents.
    if user.role == "admin":
        return document

    share = db.scalar(
        select(DocumentShare).where(
            DocumentShare.document_id == document_id,
            DocumentShare.shared_with_user_id == user.id,
        )
    )

    # Hide documents that have not been shared with this user.
    if share is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    granted_level = PERMISSION_LEVELS.get(share.permission, 0)
    required_level = PERMISSION_LEVELS.get(required_permission)

    if required_level is None:
        raise ValueError(f"Invalid permission: {required_permission}")

    if granted_level < required_level:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this document",
        )

    return document


def get_owned_document(
    document_id: int,
    user: User,
    db: Session,
) -> Document:
    """Only the owner or an admin can delete a document."""
    document = db.get(Document, document_id)

    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    if document.owner_id != user.id and user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    return document


async def save_upload(
    upload: UploadFile,
    user: User,
    db: Session,
) -> Document:
    if not upload.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename is required",
        )

    original_name = Path(upload.filename).name
    extension = Path(original_name).suffix.lower()

    if extension not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File extension is not allowed",
        )

    if upload.content_type not in ALLOWED_TYPES[extension]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File content type does not match the allowed type",
        )

    stored_filename = f"{uuid.uuid4().hex}{extension}"
    destination = UPLOAD_DIR / stored_filename
    file_size = 0

    try:
        with destination.open("wb") as output:
            while True:
                chunk = await upload.read(1024 * 1024)

                if not chunk:
                    break

                file_size += len(chunk)

                if file_size > MAX_FILE_SIZE:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail="File exceeds the 5 MB size limit",
                    )

                output.write(chunk)

        if file_size == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Empty files are not allowed",
            )

        document = Document(
            filename=original_name,
            stored_filename=stored_filename,
            file_path=str(destination),
            content_type=upload.content_type or "application/octet-stream",
            file_size=file_size,
            owner_id=user.id,
        )

        db.add(document)
        db.commit()
        db.refresh(document)

        return document

    except Exception:
        destination.unlink(missing_ok=True)
        db.rollback()
        raise

    finally:
        await upload.close()


@router.post(
    "/upload",
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    file: UploadFile = File(...),
    user: User = Depends(
        require_roles("admin", "manager", "user")
    ),
    db: Session = Depends(get_db),
):
    """Admin, manager, and user roles can upload documents."""
    document = await save_upload(file, user, db)
    return document_response(document)


@router.post(
    "/upload/multiple",
    status_code=status.HTTP_201_CREATED,
)
async def upload_multiple_documents(
    files: list[UploadFile] = File(...),
    user: User = Depends(
        require_roles("admin", "manager", "user")
    ),
    db: Session = Depends(get_db),
):
    """Upload multiple documents with role and file-count restrictions."""
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one file is required",
        )

    if len(files) > MAX_FILES_PER_REQUEST:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum 10 files per request",
        )

    documents = []

    try:
        for upload in files:
            document = await save_upload(upload, user, db)
            documents.append(document)
    finally:
        for upload in files:
            if not upload.file.closed:
                await upload.close()

    return {
        "count": len(documents),
        "documents": [
            document_response(document)
            for document in documents
        ],
    }


@router.get("")
def list_documents(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    search: str | None = Query(None, max_length=255),
    content_type: str | None = Query(None),
    sort_by: str = Query("created_at"),
    order: str = Query("desc"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List documents owned by the authenticated user."""
    sort_fields = {
        "created_at": Document.created_at,
        "filename": Document.filename,
        "file_size": Document.file_size,
    }

    if sort_by not in sort_fields:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid sort_by field",
        )

    if order not in {"asc", "desc"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="order must be asc or desc",
        )

    filters = [Document.owner_id == user.id]

    if search:
        filters.append(Document.filename.contains(search))

    if content_type:
        filters.append(Document.content_type == content_type)

    statement = select(Document).where(*filters)

    count_statement = (
        select(func.count())
        .select_from(Document)
        .where(*filters)
    )

    total = db.scalar(count_statement) or 0

    sort_column = sort_fields[sort_by]
    sort_column = (
        sort_column.desc()
        if order == "desc"
        else sort_column.asc()
    )

    statement = (
        statement
        .order_by(sort_column)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    documents = db.scalars(statement).all()

    return {
        "page": page,
        "page_size": page_size,
        "total": total,
        "documents": [
            document_response(document)
            for document in documents
        ],
    }


@router.get("/{document_id}")
def get_document(
    document_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """View a document if the user owns it or has view permission."""
    document = get_accessible_document(
        document_id=document_id,
        user=user,
        db=db,
        required_permission="view",
    )

    return document_response(document)


@router.get("/{document_id}/download")
def download_document(
    document_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Download requires download permission for shared documents."""
    document = get_accessible_document(
        document_id=document_id,
        user=user,
        db=db,
        required_permission="download",
    )

    file_path = UPLOAD_DIR / document.stored_filename

    if not file_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Stored file not found",
        )

    return FileResponse(
        path=file_path,
        media_type=document.content_type,
        filename=document.filename,
    )


@router.delete("/{document_id}")
def delete_document(
    document_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Only the owner or an admin can delete a document."""
    document = get_owned_document(document_id, user, db)
    file_path = UPLOAD_DIR / document.stored_filename

    db.delete(document)
    db.commit()

    file_path.unlink(missing_ok=True)

    return {"message": "Document deleted successfully"}
