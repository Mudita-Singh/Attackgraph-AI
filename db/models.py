import datetime
import uuid
from sqlalchemy import (
    Column, String, Text, Integer, Float, Boolean, DateTime, ForeignKey, JSON
)
from sqlalchemy.orm import relationship
from db.database import Base

def generate_uuid():
    return str(uuid.uuid4())

class Scan(Base):
    __tablename__ = "scans"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    target_url = Column(String(512), nullable=False)
    status = Column(String(50), nullable=False, default="PENDING")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    nodes = relationship("Node", back_populates="scan", cascade="all, delete-orphan")
    edges = relationship("Edge", back_populates="scan", cascade="all, delete-orphan")
    evidence = relationship("Evidence", back_populates="scan", cascade="all, delete-orphan")
    agent_logs = relationship("AgentLog", back_populates="scan", cascade="all, delete-orphan")
    human_corrections = relationship("HumanCorrection", back_populates="scan", cascade="all, delete-orphan")


class Node(Base):
    __tablename__ = "nodes"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    scan_id = Column(String(36), ForeignKey("scans.id"), nullable=False)
    label = Column(String(255), nullable=False)
    node_type = Column(String(100), nullable=False) # e.g., service, vulnerability, credential, asset
    is_critical = Column(Boolean, default=False, nullable=False) # Section 15/16 critical node analysis
    properties = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    scan = relationship("Scan", back_populates="nodes")
    source_edges = relationship("Edge", foreign_keys="Edge.source_node_id", back_populates="source_node")
    target_edges = relationship("Edge", foreign_keys="Edge.target_node_id", back_populates="target_node")
    evidence = relationship("Evidence", back_populates="node")


class Edge(Base):
    __tablename__ = "edges"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    scan_id = Column(String(36), ForeignKey("scans.id"), nullable=False)
    source_node_id = Column(String(36), ForeignKey("nodes.id"), nullable=False)
    target_node_id = Column(String(36), ForeignKey("nodes.id"), nullable=False)
    relation_type = Column(String(100), nullable=False) # e.g., EXPLOITS, HAS_VULNERABILITY, LEADS_TO
    pattern_key = Column(String(255), nullable=True, index=True) # Section 16 spec: pattern matching & stats
    confidence = Column(Float, nullable=True) # Section 11.2/11.6 path confidence score
    status = Column(String(50), nullable=False, default="unverified") # unverified, verified, refuted, human_invalidated
    verification_outcome = Column(String(100), nullable=True) # Section 34 pattern learning
    reasoning = Column(Text, nullable=True) # LLM justification
    step = Column(Integer, nullable=True) # agent step index
    properties = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    scan = relationship("Scan", back_populates="edges")
    source_node = relationship("Node", foreign_keys=[source_node_id], back_populates="source_edges")
    target_node = relationship("Node", foreign_keys=[target_node_id], back_populates="target_edges")
    evidence = relationship("Evidence", back_populates="edge")


class Evidence(Base):
    __tablename__ = "evidence"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    scan_id = Column(String(36), ForeignKey("scans.id"), nullable=False)
    node_id = Column(String(36), ForeignKey("nodes.id"), nullable=True)
    edge_id = Column(String(36), ForeignKey("edges.id"), nullable=True)
    tool_name = Column(String(100), nullable=False)
    raw_output = Column(Text, nullable=True)
    parsed_findings = Column(JSON, default=dict)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)

    scan = relationship("Scan", back_populates="evidence")
    node = relationship("Node", back_populates="evidence")
    edge = relationship("Edge", back_populates="evidence")


class AgentLog(Base):
    __tablename__ = "agent_log"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    scan_id = Column(String(36), ForeignKey("scans.id"), nullable=False)
    step_number = Column(Integer, nullable=False)
    thought = Column(Text, nullable=True)
    action = Column(Text, nullable=True)
    observation = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)

    scan = relationship("Scan", back_populates="agent_logs")


class HumanCorrection(Base):
    __tablename__ = "human_corrections"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    scan_id = Column(String(36), ForeignKey("scans.id"), nullable=False)
    target_type = Column(String(50), nullable=False) # "node" or "edge"
    target_id = Column(String(36), nullable=False)
    correction_type = Column(String(100), nullable=False) # e.g., FALSE_POSITIVE, ADD_RELATION, OVERRIDE
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    scan = relationship("Scan", back_populates="human_corrections")


class PatternStats(Base):
    __tablename__ = "pattern_stats"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    pattern_key = Column(String(255), unique=True, nullable=False, index=True)
    occurrence_count = Column(Integer, default=0, nullable=False)
    success_rate = Column(Float, default=0.0, nullable=False)
    last_observed_at = Column(DateTime, default=datetime.datetime.utcnow)
