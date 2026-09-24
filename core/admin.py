from django.contrib import admin

from .models import (
    Agent,
    AgentCapability,
    AgentTask,
    ApprovalRequest,
    AuditLog,
    Evidence,
    Finding,
    KnowledgeArticle,
    Order,
    Product,
    Report,
    ResearchProject,
    ResearchSource,
)


admin.site.register([
    ResearchProject,
    ResearchSource,
    Evidence,
    Finding,
    Report,
    Agent,
    AgentCapability,
    AgentTask,
    ApprovalRequest,
    AuditLog,
    KnowledgeArticle,
    Product,
    Order,
])
