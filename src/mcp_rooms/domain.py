"""Shared value primitives. No persistence, network, protocol or credential issuance."""
from dataclasses import dataclass
import re
import unicodedata


class DomainError(Exception):
    def __init__(self, code, **details):
        super().__init__(code)
        self.code, self.details = code, details


@dataclass(frozen=True)
class Principal:
    user_id: str
    credential_id: str
    scopes: frozenset[str]

    @property
    def owner(self):
        return 'user:' + self.user_id


def text(value, maximum):
    if not isinstance(value, str):
        raise DomainError('invalid_text')
    value = unicodedata.normalize('NFC', value).strip()
    if not value or len(value) > maximum or any(
            unicodedata.category(c) == 'Cc' and c not in '\n\t' for c in value):
        raise DomainError('invalid_text')
    return value


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(
            r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}', value):
        raise DomainError('invalid_id')
    return value
