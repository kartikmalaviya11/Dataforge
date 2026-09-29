import json
import os
import uuid
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any

@dataclass
class Visual:
    id: str
    title: str
    type: str # e.g., 'bar_chart', 'line_chart', 'scorecard'
    kpi_refs: List[str] = field(default_factory=list)
    question_refs: List[str] = field(default_factory=list)
    description: str = ""

@dataclass
class DashboardPage:
    id: str
    title: str
    visuals: List[Visual] = field(default_factory=list)
    layout: str = "grid"

@dataclass
class DashboardBlueprint:
    id: str
    title: str
    pages: List[DashboardPage] = field(default_factory=list)

class DashboardBlueprintManager:
    def __init__(self, workspace_path: str):
        self.workspace_path = workspace_path
        self.config_dir = os.path.join(self.workspace_path, '.dataforge')
        self.blueprint_file = os.path.join(self.config_dir, 'blueprints.json')
        self._ensure_config_dir()
        self.blueprints: Dict[str, DashboardBlueprint] = self._load_blueprints()

    def _ensure_config_dir(self):
        if not os.path.exists(self.config_dir):
            os.makedirs(self.config_dir)

    def _load_blueprints(self) -> Dict[str, DashboardBlueprint]:
        if not os.path.exists(self.blueprint_file):
            return {}
        try:
            with open(self.blueprint_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                blueprints = {}
                for bp_id, bp_data in data.items():
                    pages = []
                    for p_data in bp_data.get('pages', []):
                        visuals = []
                        for v_data in p_data.get('visuals', []):
                            visuals.append(Visual(**v_data))
                        p_data['visuals'] = visuals
                        pages.append(DashboardPage(**p_data))
                    bp_data['pages'] = pages
                    blueprints[bp_id] = DashboardBlueprint(**bp_data)
                return blueprints
        except json.JSONDecodeError:
            return {}
        except Exception:
            return {}

    def _save_blueprints(self):
        data = {}
        for bp_id, bp in self.blueprints.items():
            pages_data = []
            for p in bp.pages:
                visuals_data = []
                for v in p.visuals:
                    visuals_data.append({
                        'id': v.id,
                        'title': v.title,
                        'type': v.type,
                        'kpi_refs': v.kpi_refs,
                        'question_refs': v.question_refs,
                        'description': v.description
                    })
                pages_data.append({
                    'id': p.id,
                    'title': p.title,
                    'visuals': visuals_data,
                    'layout': p.layout
                })
            data[bp_id] = {
                'id': bp.id,
                'title': bp.title,
                'pages': pages_data
            }
        
        with open(self.blueprint_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)

    def generate_blueprint(self, title: str, kpis: List[Dict[str, Any]], questions: List[Dict[str, Any]]) -> DashboardBlueprint:
        bp_id = str(uuid.uuid4())
        
        overview_visuals = []
        for kpi in kpis:
            overview_visuals.append(Visual(
                id=str(uuid.uuid4()),
                title=kpi.get('name', 'Unknown KPI'),
                type='scorecard',
                kpi_refs=[kpi.get('id', '')] if 'id' in kpi else [],
                description=kpi.get('description', '')
            ))
            
        overview_page = DashboardPage(
            id=str(uuid.uuid4()),
            title="Overview",
            visuals=overview_visuals
        )
        
        details_visuals = []
        for q in questions:
            details_visuals.append(Visual(
                id=str(uuid.uuid4()),
                title=q.get('text', 'Unknown Question'),
                type='bar_chart',
                question_refs=[q.get('id', '')] if 'id' in q else []
            ))
            
        details_page = DashboardPage(
            id=str(uuid.uuid4()),
            title="Detailed Analysis",
            visuals=details_visuals
        )
        
        blueprint = DashboardBlueprint(
            id=bp_id,
            title=title,
            pages=[overview_page, details_page]
        )
        
        self.blueprints[bp_id] = blueprint
        self._save_blueprints()
        return blueprint

    def get_blueprint(self, bp_id: str) -> Optional[DashboardBlueprint]:
        return self.blueprints.get(bp_id)

    def delete_blueprint(self, bp_id: str) -> bool:
        if bp_id in self.blueprints:
            del self.blueprints[bp_id]
            self._save_blueprints()
            return True
        return False
