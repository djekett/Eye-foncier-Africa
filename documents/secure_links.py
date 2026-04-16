"""
Service de liens sécurisés pour documents fonciers — EYE-FONCIER
Génère des URLs temporaires, traçables et révocables pour l'envoi
de documents par email ou WhatsApp (conformité ARTCI).
"""
import logging
from datetime import timedelta

from django.utils import timezone

logger = logging.getLogger(__name__)


def create_secure_link(document, recipient=None, created_by=None, hours_valid=48, max_accesses=5):
    """
    Génère un lien d'accès sécurisé à durée de vie limitée.

    Args:
        document: instance de ParcelleDocument
        recipient: User destinataire (pour traçabilité)
        created_by: User qui génère le lien (admin, système)
        hours_valid: durée de validité en heures (défaut: 48h)
        max_accesses: nombre maximum d'accès autorisés (défaut: 5)

    Returns:
        SecureDocumentLink instance
    """
    from .models import SecureDocumentLink

    link = SecureDocumentLink.objects.create(
        document=document,
        recipient=recipient,
        expires_at=timezone.now() + timedelta(hours=hours_valid),
        max_accesses=max_accesses,
    )
    logger.info(
        "Lien sécurisé créé pour document '%s' (expire: %s, max: %d accès)",
        document.title, link.expires_at.strftime("%d/%m/%Y %H:%M"), max_accesses,
    )
    return link


def validate_secure_link(token):
    """
    Valide un token de lien sécurisé et incrémente le compteur d'accès.

    Args:
        token: str — token URL-safe unique

    Returns:
        ParcelleDocument si le lien est valide, None sinon
    """
    from .models import SecureDocumentLink

    try:
        link = SecureDocumentLink.objects.select_related("document").get(
            token=token,
            is_revoked=False,
        )
    except SecureDocumentLink.DoesNotExist:
        logger.warning("Lien sécurisé invalide ou révoqué : token=%s...", token[:10])
        return None

    if not link.is_valid:
        reason = "expiré" if timezone.now() > link.expires_at else "quota d'accès atteint"
        logger.warning("Lien sécurisé %s : %s", token[:10], reason)
        return None

    # Enregistrer l'accès
    link.access_count += 1
    link.accessed_at = timezone.now()
    link.save(update_fields=["access_count", "accessed_at"])

    logger.info(
        "Accès lien sécurisé pour '%s' (accès %d/%d)",
        link.document.title, link.access_count, link.max_accesses,
    )
    return link.document


def revoke_secure_link(token):
    """Révoque immédiatement un lien sécurisé (admin ou système)."""
    from .models import SecureDocumentLink

    updated = SecureDocumentLink.objects.filter(token=token).update(is_revoked=True)
    if updated:
        logger.info("Lien sécurisé révoqué : token=%s...", token[:10])
    return bool(updated)


def get_secure_url(document, recipient=None, hours_valid=48, base_url=None):
    """
    Raccourci : crée un lien sécurisé et retourne son URL complète.

    Args:
        document: ParcelleDocument instance
        recipient: User destinataire
        hours_valid: durée de validité en heures
        base_url: URL de base (ex: https://eye-foncier.ci). Lit PLATFORM_URL depuis settings si absent.

    Returns:
        str — URL complète du lien sécurisé
    """
    from django.conf import settings

    link = create_secure_link(document, recipient=recipient, hours_valid=hours_valid)
    platform_url = base_url or getattr(settings, "PLATFORM_URL", "https://eye-foncier.ci")
    return f"{platform_url}/documents/secure/{link.token}/"
