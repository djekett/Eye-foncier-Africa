"""
Modèles du coffre-fort documentaire — EYE-FONCIER
Stockage sécurisé avec traçabilité.
"""
import uuid
import secrets
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from parcelles.models import Parcelle


class ParcelleDocument(models.Model):
    """Document administratif sécurisé lié à une parcelle."""

    class DocType(models.TextChoices):
        TITRE_FONCIER = "titre_foncier", _("Titre Foncier")
        ACD = "acd", _("Arrêté de Concession Définitive (ACD)")
        CERTIFICAT = "certificat", _("Certificat de propriété")
        PLAN = "plan", _("Plan cadastral")
        PERMIS = "permis", _("Permis de construire")
        ATTESTATION = "attestation", _("Attestation villageoise")
        AUTRE = "autre", _("Autre document")

    class Confidentiality(models.TextChoices):
        PUBLIC = "public", _("Public — Visible par tous")
        BUYER_ONLY = "buyer_only", _("Acheteurs vérifiés uniquement")
        PRIVATE = "private", _("Privé — Admin seulement")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    parcelle = models.ForeignKey(
        Parcelle, on_delete=models.CASCADE, related_name="documents",
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        related_name="uploaded_documents",
    )

    doc_type = models.CharField(
        _("type de document"), max_length=30, choices=DocType.choices,
    )
    title = models.CharField(_("titre du document"), max_length=300)
    description = models.TextField(_("description"), blank=True)
    file = models.FileField(_("fichier"), upload_to="documents/secure/%Y/%m/")
    file_hash = models.CharField(
        _("hash SHA-256"), max_length=64, blank=True,
        help_text=_("Empreinte du fichier pour vérification d'intégrité."),
    )
    confidentiality = models.CharField(
        _("niveau de confidentialité"), max_length=20,
        choices=Confidentiality.choices, default=Confidentiality.BUYER_ONLY,
    )
    is_verified = models.BooleanField(
        _("vérifié"), default=False,
        help_text=_("Le document a été vérifié par un administrateur."),
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Document de parcelle")
        verbose_name_plural = _("Documents de parcelles")
        ordering = ["doc_type", "-created_at"]

    def __str__(self):
        return f"{self.get_doc_type_display()} — {self.parcelle.lot_number}"


class DocumentAccessLog(models.Model):
    """Trace chaque consultation de document."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(
        ParcelleDocument, on_delete=models.CASCADE, related_name="access_logs",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    action = models.CharField(max_length=50, default="view")
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Log consultation document")
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["document", "-timestamp"]),
        ]

    def __str__(self):
        return f"{self.user} → {self.document} @ {self.timestamp:%Y-%m-%d %H:%M}"


class SecureDocumentLink(models.Model):
    """
    Lien d'accès sécurisé à durée de vie limitée pour un document foncier.
    Utilisé lors de l'envoi de documents par email ou WhatsApp.
    Conforme aux exigences ARTCI : accès tracé, expirant, révocable.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(
        ParcelleDocument, on_delete=models.CASCADE,
        related_name="secure_links", verbose_name=_("document"),
    )
    token = models.CharField(
        _("token"), max_length=64, unique=True, db_index=True,
        help_text=_("Token aléatoire sécurisé (secrets.token_urlsafe)"),
    )
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="secure_document_links", verbose_name=_("destinataire"),
    )
    expires_at = models.DateTimeField(_("expire le"))
    access_count = models.PositiveIntegerField(_("nombre d'accès"), default=0)
    max_accesses = models.PositiveIntegerField(
        _("accès maximum"), default=5,
        help_text=_("Le lien devient invalide après ce nombre d'accès"),
    )
    is_revoked = models.BooleanField(
        _("révoqué"), default=False,
        help_text=_("Révocation manuelle par un administrateur"),
    )
    accessed_at = models.DateTimeField(_("dernier accès le"), null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Lien document sécurisé")
        verbose_name_plural = _("Liens documents sécurisés")
        ordering = ["-created_at"]

    def __str__(self):
        return f"Lien sécurisé — {self.document} (expire: {self.expires_at:%d/%m/%Y %H:%M})"

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = secrets.token_urlsafe(48)
        super().save(*args, **kwargs)

    @property
    def is_valid(self):
        """Vérifie si le lien est encore utilisable."""
        if self.is_revoked:
            return False
        if timezone.now() > self.expires_at:
            return False
        if self.access_count >= self.max_accesses:
            return False
        return True
