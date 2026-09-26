import os
import json
import time
import uuid
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field, asdict

from src.workspace import ProjectWorkspace
from src.kpi_engine import KPIManager

class InvalidStatusError(ValueError):
    pass

class InvalidTransitionError(ValueError):
    pass

@dataclass
class BusinessQuestion:
    question_id: str
    question: str
    status: str
    created_at: float
    updated_at: float
    status_history: List[Dict[str, Any]] = field(default_factory=list)
    is_archived: bool = False
    description: Optional[str] = None
    sql_query: Optional[str] = None
    pandas_analysis: Optional[str] = None
    result: Optional[str] = None
    finding: Optional[str] = None
    related_kpi_id: Optional[str] = None
    related_dashboard_visual: Optional[str] = None

    def dict(self):
        return asdict(self)

class QuestionManager:
    def __init__(self, workspace: ProjectWorkspace):
        self.workspace = workspace
        self.file_path = os.path.join(workspace.project_root, ".dataforge", "business_questions.json")
        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
        self.questions: List[BusinessQuestion] = []
        self._load()

    def _load(self):
        if not os.path.exists(self.file_path):
            self.questions = []
            return
        
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.questions = [BusinessQuestion(**q) for q in data]
        except (json.JSONDecodeError, ValueError):
            self.questions = []
            
        # Ensure deterministic ordering by created_at descending (newest first)
        self.questions.sort(key=lambda x: x.created_at, reverse=True)

    def _save(self):
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump([asdict(q) for q in self.questions], f, indent=2)

    def create_question(self, question: str) -> BusinessQuestion:
        if not question or not question.strip():
            raise ValueError("Question cannot be empty.")
            
        now = time.time()
        q = BusinessQuestion(
            question_id=str(uuid.uuid4()),
            question=question.strip(),
            status="Pending",
            status_history=[{
                "previous_status": None,
                "new_status": "Pending",
                "changed_at": now,
                "reason": "Created"
            }],
            is_archived=False,
            created_at=now,
            updated_at=now
        )
        self.questions.insert(0, q) # Insert at start for descending order
        self._save()
        return q

    def get_question(self, question_id: str) -> Optional[BusinessQuestion]:
        for q in self.questions:
            if q.question_id == question_id:
                return q
        return None

    def get_active_questions(self) -> List[BusinessQuestion]:
        return [q for q in self.questions if not q.is_archived]

    def get_archived_questions(self) -> List[BusinessQuestion]:
        return [q for q in self.questions if q.is_archived]

    def transition_status(self, question_id: str, new_status: str, reason: Optional[str] = None):
        valid_statuses = {"Pending", "Investigating", "Completed"}
        if new_status not in valid_statuses:
            raise InvalidStatusError(f"Invalid status: {new_status}")
            
        q = self.get_question(question_id)
        if not q:
            raise ValueError("Question not found")
            
        if q.status == new_status:
            raise InvalidTransitionError("Question is already in this status.")
            
        now = time.time()
        
        q.status_history.append({
            "previous_status": q.status,
            "new_status": new_status,
            "changed_at": now,
            "reason": reason
        })
        
        q.status = new_status
        q.updated_at = now
        self._save()

    def update_question(self, question_id: str, **kwargs):
        q = self.get_question(question_id)
        if not q:
            raise ValueError("Question not found")
            
        # Allowed fields for direct update
        allowed_fields = [
            "question", "description", "sql_query", "pandas_analysis", 
            "result", "finding", "related_kpi_id", "related_dashboard_visual"
        ]
        
        for k, v in kwargs.items():
            if k in allowed_fields:
                if v is not None:
                    setattr(q, k, v)
                    
        q.updated_at = time.time()
        self._save()

    def archive_question(self, question_id: str):
        q = self.get_question(question_id)
        if q:
            q.is_archived = True
            q.updated_at = time.time()
            self._save()

    def unarchive_question(self, question_id: str):
        q = self.get_question(question_id)
        if q:
            q.is_archived = False
            q.updated_at = time.time()
            self._save()

    def get_linked_kpi(self, question_id: str, kpi_manager: KPIManager) -> Optional[Any]:
        q = self.get_question(question_id)
        if not q or not q.related_kpi_id:
            return None
            
        kpis = kpi_manager.load_kpis()
        for k in kpis:
            if k.kpi_id == q.related_kpi_id:
                if getattr(k, 'is_active', True) == False:
                    return None
                return k
        return None
