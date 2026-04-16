"""
Modèles Notifications — EYE-FONCIER
Système de notifications multicanal (in-app, email, SMS, WhatsApp, push).
"""
import uuid
from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class Notification(models.Model):
    """Notification envoyée à un utilisateur via un canal donné."""

    class NotificationType(models.TextChoices):
        # Transactions
        TRANSACTION_STATUS = "transaction_status", _("Statut transaction")
        PAYMENT_CONFIRMED = "payment_confirmed", _("Paiement confirmé")
        PAYMENT_RECEIVED = "payment_received", _("Paiement reçu")
        PAYMENT_REMINDER = "payment_reminder", _("Rappel de paiement")
        ESCROW_UPDATE = "escrow_update", _("Mise à jour séquestre")
        SCORING_UPDATE = "scoring_update", _("Mise à jour scoring")
        # Vérification
        VERIFICATION_REQUESTED = "verification_requested", _("Demande de vérification")
        VERIFICATION_COMPLETED = "verification_completed", _("Vérification terminée")
        # Parcelles
        PARCELLE_PUBLISHED = "parcelle_published", _("Parcelle publiée")
        PARCELLE_VALIDATED = "parcelle_validated", _("Parcelle validée")
        PARCELLE_REJECTED = "parcelle_rejected", _("Parcelle rejetée")
        PARCELLE_INTEREST = "parcelle_interest", _("Intérêt pour une parcelle")
        # Matching & Visites
        MATCH_FOUND = "match_found", _("Correspondance trouvée")
        VISIT_REQUEST = "visit_request", _("Demande de visite")
        VISIT_CONFIRMED = "visit_confirmed", _("Visite confirmée")
        # Communication
        NEW_MESSAGE = "new_message", _("Nouveau message")
        NEW_REVIEW = "new_review", _("Nouvel avis")
        CLIENT_REQUEST = "client_request", _("Demande client")
        # Compte
        KYC_UPDATE = "kyc_update", _("Mise à jour KYC")
        DOCUMENT_READY = "document_ready", _("Document disponible")
        ACCOUNT_UPDATE = "account_update", _("Mise à jour compte")
        WELCOME = "welcome", _("Bienvenue")
        # Marketing & Engagement
        INACTIVITY_REMINDER = "inactivity_reminder", _("Rappel inactivité")
        NEWSLETTER = "newsletter", _("Newsletter")
        # Système
        SYSTEM = "system", _("Système")

    class Channel(models.TextChoices):
        INAPP = "inapp", _("In-App")
        EMAIL = "email", _("Email")
        SMS = "sms", _("SMS")
        WHATSAPP = "whatsapp", _("WhatsApp")
        PUSH = "push", _("Push")

    class Priority(models.TextChoices):
        LOW = "low", _("Basse")
        NORMAL = "normal", _("Normale")
        HIGH = "high", _("Haute")
        URGENT = "urgent", _("Urgente")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
        verbose_name=_("destinataire"),
    )
    notification_type = models.CharField(
        _("type"), max_length=30, choices=NotificationType.choices
    )
    channel = models.CharField(
        _("canal"), max_length=10, choices=Channel.choices, default=Channel.INAPP
    )
    priority = models.CharField(
        _("priorité"), max_length=10,
        choices=Priority.choices, default=Priority.NORMAL,
    )
    title = models.CharField(_("titre"), max_length=300)
    message = models.TextField(_("message"))
    data = models.JSONField(_("données"), default=dict, blank=True)

    is_read = models.BooleanField(_("lu"), default=False)
    read_at = models.DateTimeField(_("lu le"), null=True, blank=True)
    is_sent = models.BooleanField(_("envoyé"), default=False)
    sent_at = models.DateTimeField(_("envoyé le"), null=True, blank=True)
    error_message = models.TextField(_("erreur d'envoi"), blank=True)
    retry_count = models.PositiveSmallIntegerField(_("tentatives"), default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Notification")
        verbose_name_plural = _("Notifications")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["recipient", "-created_at"]),
            models.Index(fields=["is_read", "recipient"]),
            models.Index(fields=["notification_type", "-created_at"]),
            models.Index(fields=["channel", "is_sent"]),
        ]

    def __str__(self):
        return f"[{self.get_channel_display()}] {self.title} → {self.recipient}"


class NotificationPreference(models.Model):
    """Préférences de notification par utilisateur."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notification_preferences",
        verbose_name=_("utilisateur"),
    )
    email_enabled = models.BooleanField(_("notifications email"), default=True)
    sms_enabled = models.BooleanField(_("notifications SMS"), default=False)
    whatsapp_enabled = models.BooleanField(_("notifications WhatsApp"), default=False)
    push_enabled = models.BooleanField(_("notifications push"), default=True)
    inapp_enabled = models.BooleanField(_("notifications in-app"), default=True)

    # WhatsApp
    whatsapp_number = models.CharField(
        _("numéro WhatsApp"), max_length=20, blank=True, default="",
        help_text=_("Numéro au format international (ex: +225XXXXXXXXXX)"),
    )
    whatsapp_consent = models.BooleanField(
        _("consentement WhatsApp"), default=False,
        help_text=_("L'utilisateur a donné son consentement pour recevoir des messages WhatsApp"),
    )
    whatsapp_verified = models.BooleanField(
        _("WhatsApp vérifié"), default=False,
        help_text=_("Le numéro WhatsApp a été vérifié"),
    )

    quiet_hours_start = models.TimeField(
        _("début heures calmes"), null=True, blank=True,
        help_text=_("Ex: 22:00 — pas de SMS/push/WhatsApp pendant cette période"),
    )
    quiet_hours_end = models.TimeField(
        _("fin heures calmes"), null=True, blank=True,
        help_text=_("Ex: 07:00"),
    )
    disabled_types = models.JSONField(
        _("types désactivés"), default=list, blank=True,
        help_text=_("Liste des types de notification à ignorer"),
    )

    # Consentement explicite (ARTCI / opt-in)
    sms_consent = models.BooleanField(
        _("consentement SMS"), default=False,
        help_text=_("L'utilisateur a donné son consentement pour recevoir des SMS"),
    )
    marketing_consent = models.BooleanField(
        _("consentement marketing"), default=False,
        help_text=_("Accepte de recevoir newsletters et offres commerciales"),
    )
    consent_given_at = models.DateTimeField(
        _("date du consentement"), null=True, blank=True,
        help_text=_("Horodatage de l'accord pour audit ARTCI"),
    )
    unsubscribe_token = models.CharField(
        _("token de désinscription"), max_length=64,
        unique=True, null=True, blank=True, default=None,
        help_text=_("Token pour désinscription en un clic depuis les emails"),
    )

    # Token Firebase Cloud Messaging pour les notifications push
    fcm_token = models.CharField(
        _("token FCM"), max_length=500, blank=True, default="",
        help_text=_("Token Firebase Cloud Messaging du device"),
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Préférence de notification")
        verbose_name_plural = _("Préférences de notification")

    def __str__(self):
        return f"Préférences de {self.user}"


class NotificationLog(models.Model):
    """Journal d'envoi des notifications pour traçabilité et débogage."""

    class Status(models.TextChoices):
        QUEUED = "queued", _("En file d'attente")
        SENDING = "sending", _("En cours d'envoi")
        SENT = "sent", _("Envoyé")
        DELIVERED = "delivered", _("Délivré")
        FAILED = "failed", _("Échoué")
        RETRYING = "retrying", _("Nouvelle tentative")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    notification = models.ForeignKey(
        Notification, on_delete=models.CASCADE,
        related_name="logs", verbose_name=_("notification"),
    )
    status = models.CharField(
        _("statut"), max_length=10, choices=Status.choices,
    )
    channel = models.CharField(
        _("canal"), max_length=10, choices=Notification.Channel.choices,
    )
    provider = models.CharField(
        _("fournisseur"), max_length=50, blank=True,
        help_text=_("Ex: twilio, infobip, fcm, smtp"),
    )
    provider_message_id = models.CharField(
        _("ID message fournisseur"), max_length=200, blank=True,
    )
    error_detail = models.TextField(_("détail erreur"), blank=True)
    response_data = models.JSONField(
        _("réponse fournisseur"), default=dict, blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Log de notification")
        verbose_name_plural = _("Logs de notification")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["notification", "-created_at"]),
            models.Index(fields=["status", "channel"]),
        ]

    def __str__(self):
        return f"[{self.get_status_display()}] {self.channel} — {self.notification_id}"


class NotificationTemplate(models.Model):
    """
    Modèle de message réutilisable pour chaque type/canal.
    Permet à l'admin de modifier les textes sans toucher au code.
    Supporte la syntaxe Django template ({{ user_name }}, {{ parcelle_lot }}, etc.)
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.SlugField(
        _("nom interne"), max_length=100, unique=True,
        help_text=_("Identifiant unique, ex : verification_clean_fomo"),
    )
    notification_type = models.CharField(
        _("type de notification"), max_length=30,
        choices=Notification.NotificationType.choices,
    )
    channel = models.CharField(
        _("canal"), max_length=10, choices=Notification.Channel.choices,
    )
    subject = models.CharField(
        _("objet / titre"), max_length=300,
        help_text=_("Objet de l'email ou titre de la notification"),
    )
    body_template = models.TextField(
        _("corps du message"),
        help_text=_(
            "Texte du message. Utiliser la syntaxe Django template : "
            "{{ user_name }}, {{ parcelle_lot }}, {{ reference }}, {{ amount }}, {{ action_url }}"
        ),
    )
    whatsapp_content_sid = models.CharField(
        _("Content SID WhatsApp"), max_length=100, blank=True, default="",
        help_text=_("SID du template approuvé Meta/Twilio pour les messages WhatsApp hors fenêtre"),
    )
    language = models.CharField(_("langue"), max_length=10, default="fr")
    is_active = models.BooleanField(_("actif"), default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Modèle de notification")
        verbose_name_plural = _("Modèles de notification")
        ordering = ["notification_type", "channel"]
        unique_together = [("notification_type", "channel", "language")]

    def __str__(self):
        return f"{self.name} [{self.get_channel_display()}]"

    def render(self, context: dict) -> tuple[str, str]:
        """Retourne (subject, body) après rendu avec le contexte fourni."""
        from django.template import Context, Template
        body = Template(self.body_template).render(Context(context))
        subject = Template(self.subject).render(Context(context))
        return subject, body


class Campaign(models.Model):
    """
    Campagne d'envoi groupé (newsletters, re-engagement, promotionnel).
    Permet à l'admin de cibler une audience et d'envoyer en masse.
    """

    class CampaignType(models.TextChoices):
        NEWSLETTER = "newsletter", _("Newsletter")
        REENGAGEMENT = "reengagement", _("Ré-engagement")
        PROMOTIONAL = "promotional", _("Promotionnel")

    class TargetAudience(models.TextChoices):
        ALL = "all", _("Tous les utilisateurs")
        ACHETEURS = "acheteurs", _("Acheteurs")
        VENDEURS = "vendeurs", _("Vendeurs / Propriétaires")
        INACTIVE_30D = "inactive_30d", _("Inactifs 30+ jours")
        CUSTOM = "custom", _("Filtre personnalisé")

    class Status(models.TextChoices):
        DRAFT = "draft", _("Brouillon")
        SCHEDULED = "scheduled", _("Planifiée")
        SENDING = "sending", _("En cours d'envoi")
        SENT = "sent", _("Envoyée")
        CANCELLED = "cancelled", _("Annulée")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(_("nom de la campagne"), max_length=300)
    campaign_type = models.CharField(
        _("type"), max_length=20, choices=CampaignType.choices,
        default=CampaignType.NEWSLETTER,
    )
    template = models.ForeignKey(
        NotificationTemplate, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="campaigns", verbose_name=_("modèle de message"),
    )
    channels = models.JSONField(
        _("canaux"), default=list,
        help_text=_('Liste des canaux : ["email", "whatsapp", "sms"]'),
    )
    target_audience = models.CharField(
        _("audience cible"), max_length=20,
        choices=TargetAudience.choices, default=TargetAudience.ALL,
    )
    custom_filter = models.JSONField(
        _("filtre personnalisé"), default=dict, blank=True,
        help_text=_("Filtre Django ORM sérialisé pour audience avancée"),
    )
    # Contenu (override template si renseigné)
    subject = models.CharField(_("objet / titre"), max_length=300, blank=True)
    body = models.TextField(_("corps du message"), blank=True)

    status = models.CharField(
        _("statut"), max_length=15, choices=Status.choices, default=Status.DRAFT,
    )
    scheduled_at = models.DateTimeField(_("envoi planifié le"), null=True, blank=True)
    sent_at = models.DateTimeField(_("envoyée le"), null=True, blank=True)

    # Statistiques (mis à jour pendant l'envoi)
    total_recipients = models.PositiveIntegerField(_("total destinataires"), default=0)
    total_sent = models.PositiveIntegerField(_("total envoyés"), default=0)
    total_delivered = models.PositiveIntegerField(_("total délivrés"), default=0)
    total_failed = models.PositiveIntegerField(_("total échoués"), default=0)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        related_name="campaigns_created", verbose_name=_("créée par"),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Campagne")
        verbose_name_plural = _("Campagnes")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} [{self.get_status_display()}]"

    @property
    def delivery_rate(self):
        """Taux de délivrance en pourcentage."""
        if self.total_sent == 0:
            return 0
        return round((self.total_delivered / self.total_sent) * 100, 1)
