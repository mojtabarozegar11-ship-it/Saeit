from rest_framework import serializers
from .models import ResearchProject,ResearchSource,Evidence,Finding,Report,Agent,AgentTask,ApprovalRequest,KnowledgeArticle,Product,Order
class Base(serializers.ModelSerializer):
 class Meta: fields='__all__'
def make(model): return type(model.__name__+'Serializer',(Base,),{'Meta':type('Meta',(),{'model':model,'fields':'__all__'})})
ResearchProjectSerializer=make(ResearchProject); ResearchSourceSerializer=make(ResearchSource); EvidenceSerializer=make(Evidence); FindingSerializer=make(Finding); ReportSerializer=make(Report); AgentSerializer=make(Agent); AgentTaskSerializer=make(AgentTask); ApprovalRequestSerializer=make(ApprovalRequest); KnowledgeArticleSerializer=make(KnowledgeArticle); ProductSerializer=make(Product); OrderSerializer=make(Order)
