from django.conf import settings
from django.db import models
class T(models.Model):
 created_at=models.DateTimeField(auto_now_add=True); updated_at=models.DateTimeField(auto_now=True)
 class Meta: abstract=True
class ResearchProject(T):
 title=models.CharField(max_length=300); objective=models.TextField(); status=models.CharField(max_length=30,default="draft"); owner=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name="research_projects")
class ResearchSource(T):
 project=models.ForeignKey(ResearchProject,on_delete=models.CASCADE,related_name="sources"); title=models.CharField(max_length=500); url=models.URLField(blank=True); publisher=models.CharField(max_length=300,blank=True); content_hash=models.CharField(max_length=128,blank=True)
class Evidence(T):
 project=models.ForeignKey(ResearchProject,on_delete=models.CASCADE,related_name="evidence"); source=models.ForeignKey(ResearchSource,on_delete=models.CASCADE,related_name="evidence"); passage=models.TextField(); confidence=models.DecimalField(max_digits=5,decimal_places=2,null=True,blank=True)
class Finding(T):
 project=models.ForeignKey(ResearchProject,on_delete=models.CASCADE,related_name="findings"); title=models.CharField(max_length=300); statement=models.TextField(); confidence=models.DecimalField(max_digits=5,decimal_places=2,null=True,blank=True); limitation=models.TextField(blank=True); evidence=models.ManyToManyField(Evidence,blank=True,related_name="findings")
class Report(T):
 project=models.ForeignKey(ResearchProject,on_delete=models.CASCADE,related_name="reports"); title=models.CharField(max_length=300); version=models.PositiveIntegerField(default=1); status=models.CharField(max_length=30,default="draft"); content=models.JSONField(default=dict)
class Agent(T):
 code=models.SlugField(unique=True); name=models.CharField(max_length=200); mission=models.TextField(); risk_level=models.CharField(max_length=10,default="low"); active=models.BooleanField(default=False)
class AgentTask(T):
 agent=models.ForeignKey(Agent,on_delete=models.PROTECT,related_name="tasks"); project=models.ForeignKey(ResearchProject,on_delete=models.CASCADE,null=True,blank=True,related_name="agent_tasks"); input_data=models.JSONField(default=dict); output_data=models.JSONField(default=dict); status=models.CharField(max_length=20,default="queued"); cost=models.DecimalField(max_digits=12,decimal_places=4,default=0)
class ApprovalRequest(T):
 action_type=models.CharField(max_length=100); target_type=models.CharField(max_length=100); target_id=models.CharField(max_length=100); reason=models.TextField(); risk=models.CharField(max_length=10,default="high"); status=models.CharField(max_length=20,default="pending"); requested_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name="approval_requests")
class AuditLog(T):
 actor_type=models.CharField(max_length=30); actor_id=models.CharField(max_length=100,blank=True); action=models.CharField(max_length=200); target_type=models.CharField(max_length=100,blank=True); target_id=models.CharField(max_length=100,blank=True); before_state=models.JSONField(default=dict); after_state=models.JSONField(default=dict); trace_id=models.CharField(max_length=100,db_index=True)
class KnowledgeArticle(T):
 title=models.CharField(max_length=300); slug=models.SlugField(unique=True); content=models.TextField(); version=models.PositiveIntegerField(default=1); published=models.BooleanField(default=False)
class Product(T):
 title=models.CharField(max_length=300); product_type=models.CharField(max_length=50); price=models.DecimalField(max_digits=14,decimal_places=2,default=0); currency=models.CharField(max_length=10,default="IRR"); active=models.BooleanField(default=False); metadata=models.JSONField(default=dict)
class Order(T):
 customer=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name="orders"); status=models.CharField(max_length=30,default="pending"); total=models.DecimalField(max_digits=14,decimal_places=2,default=0); currency=models.CharField(max_length=10,default="IRR")
