from __future__ import annotations

import logging

import requests

from app.utils.settings import settings

logger = logging.getLogger(__name__)

class WhatsAppServiceError(RuntimeError):
    pass

class WhatsAppService:

    def __init__(
        self,
        token: str | None = None,
        phone_number_id: str | None = None,
    ):
        self.token = token or settings.meta_whatsapp_token
        self.phone_number_id = phone_number_id or settings.meta_whatsapp_phone_number_id
        self.base_url = f"https://graph.facebook.com/v22.0/{self.phone_number_id}"

    def _validate_config(self) -> None:
        if not self.token:
            raise WhatsAppServiceError("META_WHATSAPP_TOKEN não configurado")
        if not self.phone_number_id:
            raise WhatsAppServiceError("META_WHATSAPP_PHONE_NUMBER_ID não configurado")

    def _get_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    @staticmethod
    def _normalize_number(to_number: str) -> str:
        return to_number.lstrip("+")

    def send_text_message(self, to_number: str, text: str) -> dict:
        self._validate_config()

        normalized_number = self._normalize_number(to_number)
        url = f"{self.base_url}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "to": normalized_number,
            "type": "text",
            "text": {"body": text},
        }

        logger.debug(f"Enviando mensagem para {normalized_number}")
        response = requests.post(url, json=payload, headers=self._get_headers(), timeout=30)

        if response.status_code >= 400:
            raise WhatsAppServiceError(f"Erro ao enviar mensagem: {response.status_code} - {response.text}")

        logger.debug("Mensagem enviada com sucesso")
        return response.json()

    def mark_as_read(self, message_id: str) -> dict:
        self._validate_config()

        url = f"{self.base_url}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": message_id,
        }

        logger.debug(f"Marcando mensagem {message_id} como lida")
        response = requests.post(url, json=payload, headers=self._get_headers(), timeout=30)

        if response.status_code >= 400:
            logger.warning(f"Erro ao marcar mensagem como lida: {response.status_code} - {response.text}")
            return {}

        logger.debug("Mensagem marcada como lida")
        return response.json()

    def get_media_url(self, media_id: str) -> str:
        self._validate_config()

        url = f"https://graph.facebook.com/v22.0/{media_id}"
        response = requests.get(url, headers=self._get_headers(), timeout=30)

        if response.status_code >= 400:
            raise WhatsAppServiceError(f"Erro ao obter URL de mídia: {response.status_code} - {response.text}")

        return response.json().get("url", "")

whatsapp_service = WhatsAppService()
