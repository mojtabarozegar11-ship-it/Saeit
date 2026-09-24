from django.contrib import admin
from .models import *
for m in [ResearchProject,ResearchSource,Evidence,Finding,Report,Agent,AgentTask,ApprovalRequest,AuditLog,KnowledgeArticle,Product,Order]: admin.site.register(m)
