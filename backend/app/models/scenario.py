from sqlalchemy import Column, String, JSON, DateTime, Boolean, ForeignKey, Integer
from app.db import Base

class Scenario(Base):
    __tablename__ = 'scenarios'
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    category = Column(String, nullable=True)
    status = Column(String, default='DRAFT')
    created_by = Column(String, ForeignKey('users.id'), nullable=True)
    base_version_id = Column(String, nullable=True)
    date_from = Column(DateTime, nullable=True)
    date_to = Column(DateTime, nullable=True)
    objective_preset = Column(String, nullable=True)
    nl_source_text = Column(String, nullable=True)
    ai_interpretation = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False)

class ScenarioChange(Base):
    __tablename__ = 'scenario_changes'
    id = Column(String, primary_key=True)
    scenario_id = Column(String, ForeignKey('scenarios.id'))
    type = Column(String, nullable=False)
    payload = Column(JSON, nullable=False)

class OptimizationRun(Base):
    __tablename__ = 'optimization_runs'
    id = Column(String, primary_key=True)
    scenario_id = Column(String, ForeignKey('scenarios.id'))
    option_label = Column(String, nullable=True)
    strategy = Column(String, nullable=True)
    status = Column(String, nullable=False)
    metrics = Column(JSON, nullable=True)
    assignments = Column(JSON, nullable=True)
    unresolved = Column(JSON, nullable=True)
    explanations = Column(JSON, nullable=True)
    recovery = Column(JSON, nullable=True)
    solve_ms = Column(Integer, nullable=True)
    created_at = Column(DateTime, nullable=True)

class Approval(Base):
    __tablename__ = 'approvals'
    id = Column(String, primary_key=True)
    scenario_id = Column(String, ForeignKey('scenarios.id'))
    run_id = Column(String, ForeignKey('optimization_runs.id'), nullable=True)
    decided_by = Column(String, ForeignKey('users.id'), nullable=True)
    decision = Column(String, nullable=False)
    comment = Column(String, nullable=True)
    decided_at = Column(DateTime, nullable=True)

class PublishedVersion(Base):
    __tablename__ = 'published_versions'
    id = Column(String, primary_key=True)
    scenario_id = Column(String, ForeignKey('scenarios.id'))
    version_no = Column(Integer, nullable=False)
    run_id = Column(String, ForeignKey('optimization_runs.id'), nullable=True)
    published_by = Column(String, ForeignKey('users.id'), nullable=True)
    summary = Column(String, nullable=True)
    reverted = Column(Boolean, default=False)
    published_at = Column(DateTime, nullable=False)
