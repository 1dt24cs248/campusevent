from sqlalchemy import Column, String, Integer, JSON, Boolean, ForeignKey
from app.db import Base

class NavNode(Base):
    __tablename__ = 'nav_nodes'
    id = Column(String, primary_key=True)
    block_id = Column(String, ForeignKey('blocks.id'))
    floor_id = Column(String, ForeignKey('floors.id'), nullable=True)
    room_id = Column(String, ForeignKey('rooms.id'), nullable=True)
    kind = Column(String, nullable=False)

class NavEdge(Base):
    __tablename__ = 'nav_edges'
    id = Column(String, primary_key=True)
    from_node_id = Column(String, ForeignKey('nav_nodes.id'))
    to_node_id = Column(String, ForeignKey('nav_nodes.id'))
    cost = Column(Integer, default=1)
    accessible = Column(Boolean, nullable=True)

class NavConfig(Base):
    __tablename__ = 'nav_configs'
    id = Column(String, primary_key=True)
    vertical_cost = Column(Integer, default=3)
    same_floor_cost = Column(Integer, default=1)
