from rest_framework import serializers

from .models import (
    Agent, AgentCapability, AgentTask, ApprovalRequest, ChatMessage, ChatSession, Evidence, Finding,
    KnowledgeArticle, LedgerEntry, Order, OrderItem, PaymentIntent, PaymentWebhookEvent, Product, Report, ResearchProject, ResearchSource,
)


class Base(serializers.ModelSerializer):
    class Meta:
        fields = "__all__"


def make(model):
    return type(
        model.__name__ + "Serializer",
        (Base,),
        {"Meta": type("Meta", (), {"model": model, "fields": "__all__"})},
    )


ResearchProjectSerializer = make(ResearchProject)
ResearchSourceSerializer = make(ResearchSource)
EvidenceSerializer = make(Evidence)
FindingSerializer = make(Finding)
ReportSerializer = make(Report)
AgentSerializer = make(Agent)
AgentCapabilitySerializer = make(AgentCapability)
AgentTaskSerializer = make(AgentTask)
ApprovalRequestSerializer = make(ApprovalRequest)
KnowledgeArticleSerializer = make(KnowledgeArticle)
ProductSerializer = make(Product)
OrderSerializer = make(Order)
OrderItemSerializer = make(OrderItem)
PaymentIntentSerializer = make(PaymentIntent)
LedgerEntrySerializer = make(LedgerEntry)
PaymentWebhookEventSerializer = make(PaymentWebhookEvent)


class EvidenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Evidence
        fields = "__all__"

    def validate(self, attrs):
        project = attrs.get("project")
        source = attrs.get("source")
        if project is not None and source is not None and source.project_id != project.pk:
            raise serializers.ValidationError(
                {"source": "Evidence source must belong to the same research project."}
            )
        confidence = attrs.get("confidence")
        if confidence is not None and not (0 <= confidence <= 1):
            raise serializers.ValidationError(
                {"confidence": "Confidence must be between 0 and 1."}
            )
        return attrs


class FindingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Finding
        fields = "__all__"

    def validate_confidence(self, value):
        if value is not None and not (0 <= value <= 1):
            raise serializers.ValidationError("Confidence must be between 0 and 1.")
        return value


class ReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = Report
        fields = "__all__"

    def validate(self, attrs):
        project = attrs.get("project", getattr(self.instance, "project", None))
        version = attrs.get("version", getattr(self.instance, "version", 1))
        if project is not None and Report.objects.filter(
            project=project, version=version
        ).exclude(pk=getattr(self.instance, "pk", None)).exists():
            raise serializers.ValidationError(
                {"version": "This report version already exists for the project."}
            )
        return attrs


ChatSessionSerializer = make(ChatSession)
ChatMessageSerializer = make(ChatMessage)
