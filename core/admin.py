from django.contrib import admin
from django.contrib.admin import ModelAdmin
from django.http import HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import path, reverse

from .chat_runtime import MasterAgentChat
from .daily_content_models import DailyContentPlan, DailyContentDraft
from .models import (
    Agent,
    AgentCapability,
    AgentTask,
    ApprovalRequest,
    AuditLog,
    ChatMessage,
    ChatSession,
    Evidence,
    Finding,
    KnowledgeArticle,
    Order,
    Product,
    Report,
    ResearchProject,
    ResearchSource,
)


class ChatSessionAdmin(ModelAdmin):
    change_list_template = "admin/core/chatsession/change_list.html"
    list_display = ("id", "user", "title", "status", "created_at", "updated_at")
    search_fields = ("title", "user__username")
    readonly_fields = ("created_at", "updated_at")

    def get_queryset(self, request):
        return super().get_queryset(request).filter(user=request.user)

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "master-agent-chat/",
                self.admin_site.admin_view(self.chat_console),
                name="core_chatsession_master_agent_chat",
            ),
        ]
        return custom + urls

    def chat_console(self, request):
        session_id = request.GET.get("session")
        session = None
        if session_id:
            session = ChatSession.objects.filter(pk=session_id, user=request.user).first()

        if session is None:
            session = ChatSession.objects.create(
                user=request.user,
                title="Master Agent",
            )

        if request.method == "POST":
            message = str(request.POST.get("message", "")).strip()
            if message:
                MasterAgentChat().respond(session, message)
            return HttpResponseRedirect(
                f"{reverse('admin:core_chatsession_master_agent_chat')}?session={session.pk}"
            )

        messages = session.messages.order_by("created_at")
        sessions = ChatSession.objects.filter(user=request.user).order_by("-updated_at")[:30]
        context = {
            **self.admin_site.each_context(request),
            "title": "چت با Master Agent",
            "session": session,
            "messages": messages,
            "sessions": sessions,
            "opts": self.model._meta,
        }
        return TemplateResponse(
            request,
            "admin/core/master_agent_chat.html",
            context,
        )


admin.site.register(ChatSession, ChatSessionAdmin)

@admin.register(DailyContentPlan)
class DailyContentPlanAdmin(admin.ModelAdmin):
    list_display = ("run_date", "project", "status", "company_title", "ceo_title")
    list_filter = ("status", "run_date")
    search_fields = ("company_topic", "ceo_topic", "company_title", "ceo_title")


@admin.register(DailyContentDraft)
class DailyContentDraftAdmin(admin.ModelAdmin):
    list_display = ("title", "kind", "status", "plan", "knowledge_article")
    list_filter = ("kind", "status")
    search_fields = ("title", "slug")


admin.site.register([
    ResearchProject,
    ResearchSource,
    Evidence,
    Finding,
    Report,
    Agent,
    AgentCapability,
    AgentTask,
    ChatMessage,
    ApprovalRequest,
    AuditLog,
    KnowledgeArticle,
    Product,
    Order,
])
