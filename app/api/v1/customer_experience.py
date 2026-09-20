from datetime import datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_role
from app.models.customer_experience import FittingSessionStatus
from app.models.user import Role, User
from app.schemas.customer_experience import (
    ChatConversationCreate, ChatConversationResponse, ChatMessageCreate, ChatMessageResponse,
    ExecutiveAnalyticsResponse,
    RecommendationResponse,
    RecommendationStateUpdate,
    UserPreferenceResponse,
    UserPreferenceUpsert,
    VirtualFittingResultCreate,
    VirtualFittingResultResponse,
    VirtualFittingSessionCreate,
    VirtualFittingSessionResponse,
    VirtualFittingSessionStatusUpdate,
)
from app.services import customer_experience_service as service

router = APIRouter(tags=["customer-experience"])
staff = Depends(require_role(Role.ADMINISTRADOR, Role.ENCARGADO, Role.CAJERO))
privileged_roles = {Role.ADMINISTRADOR, Role.ENCARGADO, Role.CAJERO}


@router.post("/fitting/sessions", response_model=VirtualFittingSessionResponse, status_code=201)
@router.post("/virtual-fitting/sessions", response_model=VirtualFittingSessionResponse, status_code=201)
def create_fitting_session(
    data: VirtualFittingSessionCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return service.create_fitting_session(db, user.id, data)


@router.get("/fitting/sessions/{session_id}", response_model=VirtualFittingSessionResponse)
@router.get("/virtual-fitting/sessions/{session_id}", response_model=VirtualFittingSessionResponse)
def get_fitting_session(session_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return service.get_fitting_session(db, session_id, user.id, user.role in privileged_roles)


@router.post(
    "/fitting/sessions/{session_id}/results",
    response_model=VirtualFittingResultResponse,
    status_code=201,
)
@router.post("/virtual-fitting/sessions/{session_id}/results", response_model=VirtualFittingResultResponse, status_code=201)
def add_fitting_result(
    session_id: int,
    data: VirtualFittingResultCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = service.get_fitting_session(db, session_id, user.id, user.role in privileged_roles)
    return service.add_fitting_result(db, session, data)


@router.patch("/fitting/sessions/{session_id}", response_model=VirtualFittingSessionResponse)
def update_fitting_session(
    session_id: int,
    data: VirtualFittingSessionStatusUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = service.get_fitting_session(db, session_id, user.id, user.role in privileged_roles)
    return service.update_fitting_status(db, session, data.status.value)


@router.get("/recommendations/preferences", response_model=UserPreferenceResponse | None)
def get_user_preferences(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return service.get_preferences(db, user.id)


@router.put("/recommendations/preferences", response_model=UserPreferenceResponse)
def save_user_preferences(
    data: UserPreferenceUpsert,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return service.upsert_preferences(db, user.id, data)


@router.post("/recommendations", response_model=RecommendationResponse, status_code=201)
@router.post("/recommendations/generate", response_model=RecommendationResponse, status_code=201)
def generate_recommendations(
    limit: int = Query(default=10, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return service.generate_recommendations(db, user.id, limit)


@router.get("/recommendations", response_model=list[RecommendationResponse])
def list_recommendations(
    limit: int = Query(default=20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """CU18: historial de recomendaciones del cliente con su estado."""
    return service.list_recommendations(db, user.id, limit)


@router.patch("/recommendations/{recommendation_id}", response_model=RecommendationResponse)
def update_recommendation_status(
    recommendation_id: int,
    data: RecommendationStateUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """CU18: marcar el bloque de recomendaciones como visto o descartado."""
    return service.update_recommendation_status(
        db, recommendation_id, user.id, data.status, user.role in privileged_roles
    )


@router.post("/chatbot/conversations", response_model=ChatConversationResponse, status_code=201)
def create_chat_conversation(data: ChatConversationCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return service.create_chat_conversation(db, user.id, data.title, data.context)


@router.get("/chatbot/conversations", response_model=list[ChatConversationResponse])
def list_chat_conversations(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return service.list_chat_conversations(db, user.id)


@router.get("/chatbot/conversations/{conversation_id}", response_model=ChatConversationResponse)
def get_chat_conversation(conversation_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return service.get_chat_conversation(db, conversation_id, user.id, user.role in privileged_roles)


@router.post("/chatbot/conversations/{conversation_id}/messages", response_model=ChatMessageResponse, status_code=201)
def send_chat_message(conversation_id: int, data: ChatMessageCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    conversation = service.get_chat_conversation(db, conversation_id, user.id, user.role in privileged_roles)
    return service.send_chat_message(db, conversation, data.content, data.context, user)


@router.get("/analytics/executive", response_model=ExecutiveAnalyticsResponse, dependencies=[staff])
def executive_analytics(
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    db: Session = Depends(get_db),
):
    end = end_date or datetime.now(timezone.utc)
    start = start_date or (end - timedelta(days=30))
    return service.executive_analytics(db, start, end)
