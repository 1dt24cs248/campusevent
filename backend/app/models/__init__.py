from app.models.campus import Block, Floor, Room
from app.models.academic import Department, Section, Subject, Faculty, Student
from app.models.academic_content import AcademicMark, AcademicResource, SyllabusModule
from app.models.schedule import TimetableEntry, SessionOverride, SectionStrengthHistory
from app.models.availability import RoomUnavailability
from app.models.scenario import Scenario, ScenarioChange, OptimizationRun, Approval, PublishedVersion
from app.models.workflow import Notification, NotificationRead
from app.models.operations import MaintenanceTicket, TicketHistory, Event, EventRoom, Opportunity, Announcement, Assessment, CampusFAQ
from app.models.safety import Incident, IncidentStatusHistory, EmergencyConfig, EmergencyEvent, EmergencyContact
from app.models.actions import ReportHistory, FoodLocation, FoodMenu, FoodMenuItem
from app.models.navigation import NavNode, NavEdge, NavConfig
from app.models.identity import User, AuditLog, Setting
