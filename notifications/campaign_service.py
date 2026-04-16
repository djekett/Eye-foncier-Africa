"""
Service de campagnes — EYE-FONCIER
Envoi groupé de notifications vers une audience ciblée.
"""
import logging
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone

from .models import Campaign

logger = logging.getLogger(__name__)


def send_campaign(campaign_id: str) -> None:
    """
    Exécute l'envoi d'une campagne :
    1. Résout l'audience cible
    2. Envoie la notification via le service standard
    3. Met à jour les statistiques de la campagne
    """
    try:
        campaign = Campaign.objects.select_related("template", "created_by").get(pk=campaign_id)
    except Campaign.DoesNotExist:
        logger.error("Campagne %s introuvable", campaign_id)
        return

    if campaign.status not in (Campaign.Status.DRAFT, Campaign.Status.SCHEDULED, Campaign.Status.SENDING):
        logger.warning("Campagne %s déjà envoyée ou annulée (%s)", campaign.name, campaign.status)
        return

    # Marquer comme en cours
    campaign.status = Campaign.Status.SENDING
    campaign.save(update_fields=["status"])

    recipients = _resolve_audience(campaign)
    campaign.total_recipients = recipients.count()
    campaign.save(update_fields=["total_recipients"])

    # Résoudre le contenu (template ou contenu direct)
    subject, body = _resolve_content(campaign)
    channels = campaign.channels or ["email"]

    from .services import send_notification

    sent = 0
    failed = 0

    for user in recipients.iterator(chunk_size=50):
        try:
            send_notification(
                recipient=user,
                notification_type=_get_notification_type(campaign),
                title=subject,
                message=body,
                channels=channels,
                priority="low",
                data={
                    "campaign_id": str(campaign.pk),
                    "action_url": "/parcelles/",
                    "email_template": "notifications/email/newsletter.html",
                },
            )
            sent += 1
        except Exception as e:
            failed += 1
            logger.error("Échec envoi campagne %s pour %s : %s", campaign.name, user.email, e)

    campaign.total_sent = sent
    campaign.total_failed = failed
    campaign.status = Campaign.Status.SENT
    campaign.sent_at = timezone.now()
    campaign.save(update_fields=["total_sent", "total_failed", "status", "sent_at"])

    logger.info(
        "Campagne '%s' terminée : %d envoyés, %d échoués sur %d destinataires",
        campaign.name, sent, failed, campaign.total_recipients,
    )


def _resolve_audience(campaign: Campaign):
    """Retourne un queryset d'utilisateurs selon l'audience cible de la campagne."""
    User = get_user_model()
    base_qs = User.objects.filter(is_active=True)

    audience = campaign.target_audience

    if audience == Campaign.TargetAudience.ALL:
        return base_qs.filter(notification_preferences__marketing_consent=True).distinct()

    if audience == Campaign.TargetAudience.ACHETEURS:
        return base_qs.filter(
            role="acheteur",
            notification_preferences__marketing_consent=True,
        ).distinct()

    if audience == Campaign.TargetAudience.VENDEURS:
        return base_qs.filter(
            role__in=["vendeur", "promoteur"],
            notification_preferences__marketing_consent=True,
        ).distinct()

    if audience == Campaign.TargetAudience.INACTIVE_30D:
        cutoff = timezone.now() - timedelta(days=30)
        return base_qs.filter(last_login__lt=cutoff).distinct()

    if audience == Campaign.TargetAudience.CUSTOM:
        # Filtre JSON optionnel — pour un usage avancé (admin technique)
        # Format attendu : {"role": "acheteur"} → appliqué comme .filter(**custom_filter)
        custom_filter = campaign.custom_filter or {}
        if custom_filter:
            try:
                return base_qs.filter(**custom_filter).distinct()
            except Exception as e:
                logger.error("Filtre personnalisé invalide pour campagne %s : %s", campaign.name, e)

    return base_qs.none()


def _resolve_content(campaign: Campaign) -> tuple[str, str]:
    """
    Retourne (subject, body) depuis le template ou le contenu direct de la campagne.
    """
    subject = campaign.subject
    body = campaign.body

    if campaign.template and campaign.template.is_active:
        tmpl = campaign.template
        if not subject:
            subject = tmpl.subject
        if not body:
            body = tmpl.body_template

    subject = subject or f"Message de EYE-FONCIER — {campaign.name}"
    body = body or "Consultez notre plateforme pour les dernières opportunités foncières."
    return subject, body


def _get_notification_type(campaign: Campaign) -> str:
    """Mappe le type de campagne vers un NotificationType."""
    mapping = {
        Campaign.CampaignType.NEWSLETTER: "newsletter",
        Campaign.CampaignType.REENGAGEMENT: "inactivity_reminder",
        Campaign.CampaignType.PROMOTIONAL: "newsletter",
    }
    return mapping.get(campaign.campaign_type, "newsletter")
