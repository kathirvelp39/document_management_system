
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Document, DocumentShare, User
from app.routes.auth import get_current_user


router = APIRouter(prefix="/documents", tags=["Document Sharing"])


class ShareDocumentRequest(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    permission: str = Field(pattern="^(view|download|edit)$")


def get_owned_document(
    document_id: int,
    current_user: User,
    db: Session,
) -> Document:
    document = db.scalar(
        select(Document).where(
            Document.id == document_id,
            Document.owner_id == current_user.id,
        )
    )

    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    return document


@router.post("/{document_id}/share", status_code=status.HTTP_201_CREATED)
def share_document(
    document_id: int,
    request: ShareDocumentRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    document = get_owned_document(document_id, current_user, db)

    recipient = db.scalar(
        select(User).where(User.username == request.username)
    )

    if recipient is None or not recipient.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recipient not found",
        )

    if recipient.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot share a document with yourself",
        )

    existing_share = db.scalar(
        select(DocumentShare).where(
            DocumentShare.document_id == document.id,
            DocumentShare.shared_with_user_id == recipient.id,
        )
    )

    if existing_share:
        existing_share.permission = request.permission
        db.commit()
        db.refresh(existing_share)
        return {
            "message": "Document sharing permission updated",
            "document_id": document.id,
            "shared_with": recipient.username,
            "permission": existing_share.permission,
        }

    share = DocumentShare(
        document_id=document.id,
        shared_with_user_id=recipient.id,
        permission=request.permission,
    )

    db.add(share)
    db.commit()
    db.refresh(share)

    return {
        "message": "Document shared successfully",
        "document_id": document.id,
        "shared_with": recipient.username,
        "permission": share.permission,
    }


@router.get("/shared-with-me")
def list_shared_documents(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    results = db.execute(
        select(DocumentShare, Document, User)
        .join(Document, Document.id == DocumentShare.document_id)
        .join(User, User.id == Document.owner_id)
        .where(DocumentShare.shared_with_user_id == current_user.id)
    ).all()

    return [
        {
            "document_id": document.id,
            "filename": document.filename,
            "owner": owner.username,
            "permission": share.permission,
            "created_at": document.created_at,
        }
        for share, document, owner in results
    ]
