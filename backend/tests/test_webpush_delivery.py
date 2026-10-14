"""Real VAPID signing + RFC8291 encryption; only the network transport is mocked."""
import base64
import json

import http_ece
import jwt
import requests
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from pywebpush import webpush

from app.services.advertising_alerts import validate_subscription


def test_browser_can_decrypt_actual_webpush_payload(monkeypatch):
    browser_private = ec.generate_private_key(ec.SECP256R1())
    browser_public = browser_private.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    auth = b'0123456789abcdef'
    vapid = ec.generate_private_key(ec.SECP256R1())
    vapid_der = vapid.private_bytes(serialization.Encoding.DER, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    encode = lambda value: base64.urlsafe_b64encode(value).decode().rstrip('=')
    subscription = validate_subscription({'endpoint': 'https://fcm.googleapis.com/fcm/send/test',
                                         'keys': {'p256dh': encode(browser_public), 'auth': encode(auth)}})
    captured = {}

    def request(self, method, url, **kwargs):
        captured.update(kwargs)
        assert method.upper() == 'POST' and url == subscription['endpoint']
        response = requests.Response()
        response.status_code = 201
        response._content = b''
        return response

    monkeypatch.setattr(requests.Session, 'request', request)
    message = {'title': 'Освободилось место для рекламы', 'body': 'Баннер стоит 1 € в день.', 'url': 'https://example.org/#/publicidad/nueva'}
    webpush(subscription_info=subscription, data=json.dumps(message), vapid_private_key=encode(vapid_der),
            vapid_claims={'sub': 'mailto:noreply@example.org'}, timeout=5, ttl=300)
    plaintext = http_ece.decrypt(captured['data'], private_key=browser_private, auth_secret=auth, version='aes128gcm')
    assert json.loads(plaintext) == message
    assert any(name.lower() == 'authorization' for name in captured['headers'])
    authorization = next(value for name, value in captured['headers'].items() if name.lower() == 'authorization')
    token = authorization.split('t=', 1)[1].split(',', 1)[0]
    claims = jwt.decode(token, vapid.public_key(), algorithms=['ES256'], audience='https://fcm.googleapis.com')
    assert claims['sub'] == 'mailto:noreply@example.org'
