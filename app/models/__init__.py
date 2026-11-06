"""
Models package — imports all models so Flask-Migrate can detect them.
"""

from app.models.user import User
from app.models.beneficiary import Beneficiary, BeneficiaryHousehold
from app.models.inventory import InventoryItem, Warehouse, StockMovement
from app.models.distribution import DistributionRecord, DistributionBatch
from app.models.route import DeliveryRoute, RouteStop
from app.models.audit import AuditLog
from app.models.zone import State, LocalGovernmentArea, DistributionPoint
