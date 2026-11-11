"""
WhatsApp Dispatch & Messaging Integration Service for AgriBOS ERP.
Supports:
1. Browser/Direct Web WhatsApp Link Generation (wa.me / api.whatsapp.com)
2. Meta WhatsApp Cloud API Direct Dispatch (when WHATSAPP_API_ENABLED=True)
3. Twilio WhatsApp REST Dispatch (fallback provider)
"""

import json
import logging
import os
import re
import urllib.parse
import urllib.request
from typing import Dict, Any, Optional

logger = logging.getLogger('expense_tracking.whatsapp')


def clean_phone_number(phone: Optional[str]) -> str:
    """
    Cleans and formats a phone number for WhatsApp.
    Ensures standard Indian country code (91) prefix for 10-digit mobile numbers.
    """
    if not phone:
        return ""
    digits = re.sub(r'\D', '', str(phone))
    if not digits:
        return ""
    if len(digits) == 11 and digits.startswith('0'):
        digits = digits[1:]
    if len(digits) == 10:
        return f"91{digits}"
    if len(digits) == 12 and digits.startswith('91'):
        return digits
    return digits


def build_whatsapp_web_url(phone: Optional[str], message: str) -> str:
    """
    Generates a secure pre-filled WhatsApp Web / Mobile redirect URL.
    """
    clean_phone = clean_phone_number(phone)
    encoded = urllib.parse.quote(message)
    if clean_phone:
        return f"https://api.whatsapp.com/send?phone={clean_phone}&text={encoded}"
    return f"https://api.whatsapp.com/send?text={encoded}"


def send_direct_whatsapp_message(phone: str, message: str) -> Dict[str, Any]:
    """
    Dispatches a direct WhatsApp message via Meta Cloud API or Twilio.
    Returns status dict: {'success': bool, 'provider': str, 'error': str, 'message_id': str}
    """
    is_enabled = os.getenv('WHATSAPP_API_ENABLED', 'False').lower() in ('true', '1', 'yes')
    clean_phone = clean_phone_number(phone)

    if not is_enabled:
        return {
            'success': False,
            'provider': 'none',
            'error': 'Direct WhatsApp API is not enabled in settings. Use web WhatsApp link.',
            'clean_phone': clean_phone,
        }

    if not clean_phone:
        return {
            'success': False,
            'provider': 'none',
            'error': 'Recipient phone number is invalid or missing.',
        }

    provider = os.getenv('WHATSAPP_API_PROVIDER', 'meta').lower()

    if provider == 'meta':
        phone_number_id = os.getenv('WHATSAPP_PHONE_NUMBER_ID', '').strip()
        access_token = os.getenv('WHATSAPP_ACCESS_TOKEN', '').strip()

        if not phone_number_id or not access_token:
            return {
                'success': False,
                'provider': 'meta',
                'error': 'Missing WHATSAPP_PHONE_NUMBER_ID or WHATSAPP_ACCESS_TOKEN in environment.',
            }

        url = f"https://graph.facebook.com/v19.0/{phone_number_id}/messages"
        headers = {
            'Authorization': f"Bearer {access_token}",
            'Content-Type': 'application/json',
        }
        payload = {
            'messaging_product': 'whatsapp',
            'recipient_type': 'individual',
            'to': clean_phone,
            'type': 'text',
            'text': {
                'preview_url': False,
                'body': message,
            },
        }

        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode('utf-8'),
                headers=headers,
                method='POST',
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                msgs = data.get('messages') or [{}]
                message_id = msgs[0].get('id', '') if msgs else ''
                logger.info(f"WhatsApp Cloud API message sent to {clean_phone} (ID: {message_id})")
                return {
                    'success': True,
                    'provider': 'meta',
                    'message_id': message_id,
                }
        except Exception as exc:
            logger.error(f"Failed to dispatch WhatsApp Cloud API message to {clean_phone}: {exc}")
            return {
                'success': False,
                'provider': 'meta',
                'error': str(exc),
            }

    return {
        'success': False,
        'provider': provider,
        'error': f"Unsupported WhatsApp API provider: {provider}",
    }
