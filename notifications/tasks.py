"""
Tâches Celery — Notifications EYE-FONCIER
Envoi asynchrone des notifications via tous les canaux.
"""
import logging

from celery import shared_task

logger = logging.getLogger(__name__)

# Retry : 3 tentatives avec backoff exponentiel (30s, 60s, 120s)
RETRY_KWARGS = {
    "max_retries": 3,
    "default_retry_delay": 30,
    "retry_backoff": True,
    "retry_backoff_max": 300,
}


@shared_task(bind=True, ignore_result=True, **RETRY_KWARGS)
def send_notification_async(self, recipient_id, notification_type, title, message,
                            data=None, channels=None, priority="normal"):
    """
    Tâche principale : envoie une notification via les canaux activés.
    Appelée en asynchrone depuis les signaux et services.
    """
    try:
        from .services import send_notification
        from django.contrib.auth import get_user_model

        User = get_user_model()
        recipient = User.objects.get(pk=recipient_id)

        send_notification(
            recipient=recipient,
            notification_type=notification_type,
            title=title,
            message=message,
            data=data,
            channels=channels,
            priority=priority,
        )

    except Exception as exc:
        logger.error("Échec tâche notification pour %s : %s", recipient_id, exc)
        raise self.retry(exc=exc)


@shared_task(bind=True, ignore_result=True, **RETRY_KWARGS)
def send_email_notification(self, notification_id):
    """Envoie un email pour une notification existante."""
    try:
        from .models import Notification
        from .services import _dispatch_email

        notification = Notification.objects.get(pk=notification_id)
        _dispatch_email(notification)

    except Exception as exc:
        logger.error("Échec envoi email pour notification %s : %s", notification_id, exc)
        raise self.retry(exc=exc)


@shared_task(bind=True, ignore_result=True, **RETRY_KWARGS)
def send_whatsapp_notification(self, notification_id):
    """Envoie un message WhatsApp pour une notification existante."""
    try:
        from .models import Notification
        from .whatsapp_service import send_whatsapp

        notification = Notification.objects.get(pk=notification_id)
        success = send_whatsapp(notification)
        if not success and notification.retry_count < 3:
            raise Exception("WhatsApp non envoyé, retry programmé")

    except Exception as exc:
        logger.error("Échec envoi WhatsApp pour notification %s : %s", notification_id, exc)
        raise self.retry(exc=exc)


@shared_task(bind=True, ignore_result=True, **RETRY_KWARGS)
def send_sms_notification(self, notification_id):
    """Envoie un SMS pour une notification existante."""
    try:
        from .models import Notification
        from .services import _dispatch_sms

        notification = Notification.objects.get(pk=notification_id)
        _dispatch_sms(notification)

    except Exception as exc:
        logger.error("Échec envoi SMS pour notification %s : %s", notification_id, exc)
        raise self.retry(exc=exc)


@shared_task(ignore_result=True)
def send_welcome_notification(user_id):
    """Envoie les notifications de bienvenue à un nouvel utilisateur."""
    try:
        from django.contrib.auth import get_user_model
        from .services import send_notification

        User = get_user_model()
        user = User.objects.get(pk=user_id)
        user_name = user.first_name or user.email.split("@")[0]

        send_notification(
            recipient=user,
            notification_type="welcome",
            title="Bienvenue sur EYE-FONCIER !",
            message=(
                f"Bonjour {user_name}, votre compte a été créé avec succès. "
                "Explorez notre plateforme pour découvrir des parcelles de qualité "
                "et gérer vos transactions foncières en toute sécurité."
            ),
            data={
                "action_url": "/compte/dashboard/",
                "email_template": "notifications/email/welcome.html",
            },
        )

    except Exception as exc:
        logger.error("Échec notification bienvenue pour %s : %s", user_id, exc)


@shared_task(ignore_result=True)
def retry_failed_notifications():
    """
    Tâche périodique : retente les notifications échouées.
    Exécutée toutes les 5 minutes via Celery Beat.
    """
    from .models import Notification

    failed = Notification.objects.filter(
        is_sent=False,
        retry_count__lt=3,
        error_message__gt="",
    ).exclude(
        channel=Notification.Channel.INAPP,
    ).order_by("created_at")[:50]

    for notif in failed:
        channel = notif.channel
        if channel == Notification.Channel.EMAIL:
            send_email_notification.delay(str(notif.pk))
        elif channel == Notification.Channel.WHATSAPP:
            send_whatsapp_notification.delay(str(notif.pk))
        elif channel == Notification.Channel.SMS:
            send_sms_notification.delay(str(notif.pk))

    if failed:
        logger.info("Retry programmé pour %d notifications échouées", len(failed))


@shared_task(ignore_result=True)
def cleanup_old_notifications():
    """
    Tâche périodique : supprime les notifications lues de plus de 90 jours.
    Exécutée une fois par jour via Celery Beat.
    """
    from datetime import timedelta
    from django.utils import timezone
    from .models import Notification

    cutoff = timezone.now() - timedelta(days=90)
    deleted_count, _ = Notification.objects.filter(
        is_read=True,
        created_at__lt=cutoff,
    ).delete()

    if deleted_count:
        logger.info("Nettoyage : %d anciennes notifications supprimées", deleted_count)


@shared_task(ignore_result=True)
def cleanup_old_logs():
    """Supprime les logs de notification de plus de 180 jours."""
    from datetime import timedelta
    from django.utils import timezone
    from .models import NotificationLog

    cutoff = timezone.now() - timedelta(days=180)
    deleted_count, _ = NotificationLog.objects.filter(
        created_at__lt=cutoff,
    ).delete()

    if deleted_count:
        logger.info("Nettoyage : %d anciens logs supprimés", deleted_count)


@shared_task(ignore_result=True)
def check_inactive_users():
    """
    Tâche périodique (quotidienne) : identifie les utilisateurs inactifs
    depuis 30+ jours et envoie un message WhatsApp de ré-engagement.
    Évite de re-contacter un utilisateur déjà relancé dans les 30 derniers jours.
    """
    from datetime import timedelta
    from django.utils import timezone
    from django.contrib.auth import get_user_model
    from .services import send_notification

    User = get_user_model()
    cutoff_30d = timezone.now() - timedelta(days=30)

    # Utilisateurs inactifs depuis 30j (last_login null = jamais connecté non inclus)
    inactive_users = (
        User.objects.filter(
            last_login__lt=cutoff_30d,
            is_active=True,
        )
        .exclude(
            # Ne pas re-contacter si déjà relancé dans les 30 derniers jours
            notifications__notification_type="inactivity_reminder",
            notifications__created_at__gt=cutoff_30d,
        )
        .distinct()[:100]  # Batch de 100 max pour éviter les surcharges
    )

    sent = 0
    for user in inactive_users:
        user_name = user.first_name or user.email.split("@")[0]
        try:
            send_notification(
                recipient=user,
                notification_type="inactivity_reminder",
                title="Vous nous manquez sur EYE-FONCIER !",
                message=(
                    f"Bonjour {user_name}, cela fait un moment que vous n'avez pas visité "
                    f"EYE-FONCIER. De nouvelles parcelles sécurisées sont disponibles "
                    f"dans votre zone d'intérêt. Venez découvrir les meilleures opportunités !"
                ),
                channels=["whatsapp"],
                priority="low",
                data={
                    "action_url": "/parcelles/",
                    "email_template": "notifications/email/reengagement.html",
                },
            )
            sent += 1
        except Exception as e:
            logger.error("Échec ré-engagement pour %s : %s", user.email, e)

    if sent:
        logger.info("Ré-engagement : %d utilisateurs contactés", sent)


@shared_task(ignore_result=True)
def send_new_lots_newsletter():
    """
    Tâche hebdomadaire (lundi 9h) : newsletter des nouveaux terrains sécurisés
    publiés dans les 7 derniers jours, envoyée aux utilisateurs avec marketing_consent=True.
    """
    from datetime import timedelta
    from django.utils import timezone
    from django.contrib.auth import get_user_model
    from .services import send_notification
    from .models import Campaign, NotificationPreference

    try:
        from parcelles.models import Parcelle
    except ImportError:
        logger.warning("App parcelles introuvable pour la newsletter")
        return

    one_week_ago = timezone.now() - timedelta(days=7)
    new_parcelles = list(
        Parcelle.objects.filter(
            created_at__gte=one_week_ago,
            is_validated=True,
        ).order_by("-created_at")[:10]
    )

    if not new_parcelles:
        logger.info("Newsletter : aucune nouvelle parcelle cette semaine")
        return

    User = get_user_model()
    # Uniquement les utilisateurs ayant consenti aux messages marketing
    recipients = User.objects.filter(
        notification_preferences__marketing_consent=True,
        is_active=True,
    ).distinct()

    if not recipients.exists():
        logger.info("Newsletter : aucun destinataire avec marketing_consent")
        return

    # Créer une campagne pour tracker la livraison
    campaign = Campaign.objects.create(
        name=f"Newsletter — {timezone.now().strftime('%d/%m/%Y')}",
        campaign_type=Campaign.CampaignType.NEWSLETTER,
        channels=["email"],
        target_audience=Campaign.TargetAudience.ALL,
        subject=f"🏡 {len(new_parcelles)} nouveaux terrains sécurisés disponibles",
        body=f"{len(new_parcelles)} nouvelles parcelles validées ont été ajoutées cette semaine.",
        status=Campaign.Status.SENDING,
        total_recipients=recipients.count(),
    )

    # Construire le résumé des parcelles pour le message
    parcelles_summary = ", ".join(
        f"{p.lot_number} ({p.surface_m2} m² — {p.price:,} FCFA)"
        for p in new_parcelles[:5]
    )
    full_message = (
        f"{len(new_parcelles)} nouveaux terrains sécurisés viennent d'être validés "
        f"sur EYE-FONCIER : {parcelles_summary}. "
        f"Consultez notre catalogue pour voir tous les terrains disponibles."
    )

    sent = 0
    failed = 0
    for user in recipients.iterator():
        try:
            send_notification(
                recipient=user,
                notification_type="newsletter",
                title=f"🏡 {len(new_parcelles)} nouveaux terrains sécurisés disponibles",
                message=full_message,
                channels=["email"],
                priority="low",
                data={
                    "action_url": "/parcelles/",
                    "email_template": "notifications/email/newsletter.html",
                    "parcelles_count": len(new_parcelles),
                    "campaign_id": str(campaign.pk),
                },
            )
            sent += 1
        except Exception as e:
            failed += 1
            logger.error("Échec newsletter pour %s : %s", user.email, e)

    # Mettre à jour les stats de la campagne
    campaign.total_sent = sent
    campaign.total_failed = failed
    campaign.status = Campaign.Status.SENT
    campaign.sent_at = timezone.now()
    campaign.save(update_fields=["total_sent", "total_failed", "status", "sent_at"])

    logger.info("Newsletter envoyée : %d succès, %d échecs", sent, failed)


@shared_task(ignore_result=True)
def send_campaign_task(campaign_id):
    """Lance l'envoi asynchrone d'une campagne (depuis l'admin)."""
    from .campaign_service import send_campaign
    send_campaign(campaign_id)
