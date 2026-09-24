from rest_framework import viewsets
from .models import *
from .serializers import *
def vs(model,serializer): return type(model.__name__+'ViewSet',(viewsets.ModelViewSet,),{'queryset':model.objects.all(),'serializer_class':serializer})
ResearchProjectViewSet=vs(ResearchProject,ResearchProjectSerializer); ResearchSourceViewSet=vs(ResearchSource,ResearchSourceSerializer); EvidenceViewSet=vs(Evidence,EvidenceSerializer); FindingViewSet=vs(Finding,FindingSerializer); ReportViewSet=vs(Report,ReportSerializer); AgentViewSet=vs(Agent,AgentSerializer); AgentTaskViewSet=vs(AgentTask,AgentTaskSerializer); ApprovalRequestViewSet=vs(ApprovalRequest,ApprovalRequestSerializer); KnowledgeArticleViewSet=vs(KnowledgeArticle,KnowledgeArticleSerializer); ProductViewSet=vs(Product,ProductSerializer); OrderViewSet=vs(Order,OrderSerializer)
