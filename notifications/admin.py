"""Admin Notifications — EYE-FONCIER."""
from django.contrib import admin
from django.db.models import Count, Q
from django.utils import timezone
from django.utils.html import format_html
from .models import Campaign, Notification, NotificationLog, NotificationPreference, NotificationTemplate


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = [
        "title_short",
        "recipient",
        "type_badge",
        "channel_badge",
        "priority_badge",
        "is_read",
        "is_sent",
        "retry_count",
        "created_at",
    ]
    list_filter = [
        "notification_type",
        "channel",
        "priority",
        "is_read",
        "is_sent",
        "created_at",
    ]
    search_fields = ["title", "recipient__email", "recipient__first_name"]
    readonly_fields = [
        "id",
        "recipient",
        "notification_type",
        "channel",
        "priority",
        "title",
        "message",
        "data",
        "is_read",
        "read_at",
        "is_sent",
        "sent_at",
        "error_message",
        "retry_count",
        "created_at",
    ]
    list_per_page = 50

    def title_short(self, obj):
        return obj.title[:60] + ("..." if len(obj.title) > 60 else "")

    title_short.short_description = "Titre"

    def type_badge(self, obj):
        colors = {
            "transaction_status": "#2563eb",
            "payment_confirmed": "#16a34a",
            "payment_reminder": "#f59e0b",
            "match_found": "#8b5cf6",
            "visit_request": "#0891b2",
            "visit_confirmed": "#0891b2",
            "kyc_update": "#64748b",
            "escrow_update": "#ea580c",
            "parcelle_published": "#059669",
            "parcelle_validated": "#16a34a",
            "parcelle_rejected": "#dc2626",
            "parcelle_interest": "#7c3aed",
            "new_message": "#2563eb",
            "new_review": "#d97706",
            "client_request": "#0284c7",
            "account_update": "#475569",
            "welcome": "#10b981",
            "system": "#374151",
        }
        display = str(obj.get_notification_type_display())
        color = colors.get(obj.notification_type, "#6b7280")
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;border-radius:10px;font-size:11px">{}</span>',
            color,
            display,
        )

    type_badge.short_description = "Type"

    def channel_badge(self, obj):
        icons = {
            "inapp": "bell",
            "email": "envelope",
            "sms": "phone",
            "whatsapp": "comment-dots",
            "push": "broadcast",
        }
        colors = {
            "inapp": "#6b7280",
            "email": "#2563eb",
            "sms": "#059669",
            "whatsapp": "#25D366",
            "push": "#f59e0b",
        }
        icon = icons.get(obj.channel, "circle")
        color = colors.get(obj.channel, "#6b7280")
        return format_html(
            '<i class="fas fa-{}" style="color:{}" title="{}"></i>',
            icon,
            color,
            str(obj.get_channel_display()),
        )

    channel_badge.short_description = "Canal"

    def priority_badge(self, obj):
        colors = {
            "low": "#9ca3af",
            "normal": "#3b82f6",
            "high": "#f59e0b",
            "urgent": "#ef4444",
        }
        color = colors.get(obj.priority, "#6b7280")
        return format_html(
            '<span style="color:{};font-weight:600;font-size:11px">{}</span>',
            color,
            str(obj.get_priority_display()),
        )

    priority_badge.short_description = "Priorité"

    def has_add_permission(self, request):
        return False

    # Ajouter les nouveaux types dans les couleurs des badges
    type_badge.short_description = "Type"


@admin.register(NotificationTemplate)
class NotificationTemplateAdmin(admin.ModelAdmin):
    """CRUD complet pour les modèles de messages — modifiable sans code."""

    list_display = [
        "name",
        "type_badge",
        "channel_badge",
        "language",
        "is_active",
        "updated_at",
    ]
    list_filter = ["channel", "notification_type", "is_active", "language"]
    search_fields = ["name", "subject", "body_template"]
    list_per_page = 25

    fieldsets = (
        ("Identification", {
            "fields": ("name", "notification_type", "channel", "language", "is_active"),
        }),
        ("Contenu du message", {
            "fields": ("subject", "body_template"),
            "description": (
                "Variables disponibles : {{ user_name }}, {{ user_email }}, "
                "{{ parcelle_lot }}, {{ reference }}, {{ amount }}, "
                "{{ action_url }}, {{ platform_url }}, {{ unsubscribe_token }}"
            ),
        }),
        ("WhatsApp (optionnel)", {
            "fields": ("whatsapp_content_sid",),
            "classes": ("collapse",),
            "description": "SID du template approuvé Meta/Twilio pour messages hors fenêtre 24h",
        }),
    )
    readonly_fields = ["created_at", "updated_at"]

    def type_badge(self, obj):
        return format_html(
            '<span style="background:#2563eb;color:#fff;padding:2px 8px;border-radius:10px;font-size:11px">{}</span>',
            str(obj.get_notification_type_display()),
        )
    type_badge.short_description = "Type"

    def channel_badge(self, obj):
        colors = {
            "inapp": "#6b7280", "email": "#2563eb", "sms": "#059669",
            "whatsapp": "#25D366", "push": "#f59e0b",
        }
        color = colors.get(obj.channel, "#6b7280")
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;border-radius:10px;font-size:11px">{}</span>',
            color,
            str(obj.get_channel_display()),
        )
    channel_badge.short_description = "Canal"

    actions = ["duplicate_template"]

    def duplicate_template(self, request, queryset):
        """Duplique les templates sélectionnés (utile pour créer des variantes)."""
        import uuid as _uuid
        for tmpl in queryset:
            tmpl.pk = None
            tmpl.name = f"{tmpl.name}-copie-{str(_uuid.uuid4())[:8]}"
            tmpl.is_active = False
            tmpl.save()
        self.message_user(request, f"{queryset.count()} modèle(s) dupliqué(s) avec succès.")
    duplicate_template.short_description = "Dupliquer les modèles sélectionnés"


@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    """Gestion des campagnes d'envoi groupé."""

    list_display = [
        "name",
        "campaign_type",
        "status_badge",
        "target_audience",
        "total_recipients",
        "delivery_stats",
        "scheduled_at",
        "sent_at",
    ]
    list_filter = ["status", "campaign_type", "target_audience", "created_at"]
    search_fields = ["name", "subject"]
    list_per_page = 20
    readonly_fields = [
        "total_recipients", "total_sent", "total_delivered", "total_failed",
        "sent_at", "created_at", "updated_at", "delivery_rate_display",
    ]

    fieldsets = (
        ("Identification", {
            "fields": ("name", "campaign_type", "created_by"),
        }),
        ("Ciblage", {
            "fields": ("target_audience", "custom_filter", "channels"),
        }),
        ("Contenu", {
            "fields": ("template", "subject", "body"),
            "description": "Le contenu du template sera utilisé si subject/body sont vides.",
        }),
        ("Planification", {
            "fields": ("status", "scheduled_at"),
        }),
        ("Statistiques (lecture seule)", {
            "fields": (
                "total_recipients", "total_sent", "total_delivered",
                "total_failed", "delivery_rate_display", "sent_at",
            ),
            "classes": ("collapse",),
        }),
    )

    actions = ["launch_campaign", "cancel_campaign"]

    def status_badge(self, obj):
        colors = {
            "draft": "#9ca3af", "scheduled": "#3b82f6", "sending": "#f59e0b",
            "sent": "#16a34a", "cancelled": "#ef4444",
        }
        color = colors.get(obj.status, "#6b7280")
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;border-radius:10px;font-size:11px">{}</span>',
            color,
            str(obj.get_status_display()),
        )
    status_badge.short_description = "Statut"

    def delivery_stats(self, obj):
        if obj.total_sent == 0:
            return "—"
        return format_html(
            '<span title="{} envoyés / {} échoués" style="font-size:11px">'
            '✅ {} | ❌ {}</span>',
            obj.total_sent, obj.total_failed,
            obj.total_sent, obj.total_failed,
        )
    delivery_stats.short_description = "Livraison"

    def delivery_rate_display(self, obj):
        return f"{obj.delivery_rate}%"
    delivery_rate_display.short_description = "Taux de livraison"

    def launch_campaign(self, request, queryset):
        """Lance l'envoi asynchrone des campagnes sélectionnées (statut draft)."""
        from .tasks import send_campaign_task
        launched = 0
        for campaign in queryset.filter(status__in=["draft", "scheduled"]):
            campaign.status = Campaign.Status.SENDING
            campaign.save(update_fields=["status"])
            send_campaign_task.delay(str(campaign.pk))
            launched += 1
        self.message_user(request, f"{launched} campagne(s) lancée(s) en envoi.")
    launch_campaign.short_description = "🚀 Lancer l'envoi des campagnes sélectionnées"

    def cancel_campaign(self, request, queryset):
        """Annule les campagnes en brouillon ou planifiées."""
        cancelled = queryset.filter(status__in=["draft", "scheduled"]).update(
            status=Campaign.Status.CANCELLED
        )
        self.message_user(request, f"{cancelled} campagne(s) annulée(s).")
    cancel_campaign.short_description = "Annuler les campagnes sélectionnées"


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = [
        "user",
        "email_enabled",
        "sms_enabled",
        "sms_consent",
        "whatsapp_enabled",
        "whatsapp_consent",
        "whatsapp_verified",
        "marketing_consent",
        "push_enabled",
        "inapp_enabled",
        "consent_given_at",
    ]
    list_filter = [
        "email_enabled",
        "sms_enabled",
        "sms_consent",
        "whatsapp_enabled",
        "whatsapp_consent",
        "whatsapp_verified",
        "marketing_consent",
        "push_enabled",
    ]
    search_fields = ["user__email", "user__first_name"]
    readonly_fields = ["whatsapp_verified", "consent_given_at", "unsubscribe_token"]


@admin.register(NotificationLog)
class NotificationLogAdmin(admin.ModelAdmin):
    list_display = [
        "notification_short",
        "status_badge",
        "channel_badge",
        "provider",
        "provider_message_id_short",
        "created_at",
    ]
    list_filter = ["status", "channel", "provider", "created_at"]
    search_fields = [
        "notification__title",
        "notification__recipient__email",
        "provider_message_id",
    ]
    readonly_fields = [
        "id",
        "notification",
        "status",
        "channel",
        "provider",
        "provider_message_id",
        "error_detail",
        "response_data",
        "created_at",
    ]
    list_per_page = 50

    def notification_short(self, obj):
        title = obj.notification.title
        return title[:50] + ("..." if len(title) > 50 else "")

    notification_short.short_description = "Notification"

    def status_badge(self, obj):
        colors = {
            "queued": "#6b7280",
            "sending": "#3b82f6",
            "sent": "#16a34a",
            "delivered": "#059669",
            "failed": "#ef4444",
            "retrying": "#f59e0b",
        }
        color = colors.get(obj.status, "#6b7280")
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;border-radius:10px;font-size:11px">{}</span>',
            color,
            str(obj.get_status_display()),
        )

    status_badge.short_description = "Statut"

    def channel_badge(self, obj):
        return format_html(
            '<span style="font-size:11px">{}</span>',
            str(obj.get_channel_display()),
        )

    channel_badge.short_description = "Canal"

    def provider_message_id_short(self, obj):
        mid = obj.provider_message_id
        if len(mid) > 20:
            return mid[:20] + "..."
        return mid

    provider_message_id_short.short_description = "ID Message"

    def has_add_permission(self, request):
        return False

    def changelist_view(self, request, extra_context=None):
        """Affiche un mini-dashboard de livraison (30 derniers jours) au-dessus de la liste."""
        from datetime import timedelta
        extra_context = extra_context or {}

        since = timezone.now() - timedelta(days=30)
        stats_qs = (
            NotificationLog.objects.filter(created_at__gte=since)
            .values("channel", "status")
            .annotate(count=Count("id"))
            .order_by("channel", "status")
        )

        channel_labels = {
            "email": "Email", "sms": "SMS",
            "whatsapp": "WhatsApp", "push": "Push", "inapp": "In-App",
        }
        channel_stats = {}
        for s in stats_qs:
            ch = s["channel"]
            label = channel_labels.get(ch, ch.capitalize())
            if label not in channel_stats:
                channel_stats[label] = {"sent": 0, "delivered": 0, "failed": 0}
            if s["status"] in ("sent", "delivered"):
                channel_stats[label]["sent"] += s["count"]
            if s["status"] == "delivered":
                channel_stats[label]["delivered"] += s["count"]
            if s["status"] == "failed":
                channel_stats[label]["failed"] += s["count"]

        extra_context["channel_stats"] = channel_stats
        extra_context["stats_period"] = "30 derniers jours"
        return super().changelist_view(request, extra_context=extra_context)
