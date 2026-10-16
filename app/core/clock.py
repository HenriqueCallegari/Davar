"""Relogio da aplicacao no fuso do usuario (padrao: America/Sao_Paulo).

O servidor (Render) roda em UTC; usar `datetime.now()` direto contaria a leitura
das 22h de Brasilia como do dia seguinte e quebraria a sequencia de dias.
Retorna datetimes "ingenuos" (sem tzinfo) no horario local, mantendo o mesmo
formato ISO ja gravado nos bancos.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from app.config import Config

try:
    from zoneinfo import ZoneInfo
    _TZ = ZoneInfo(Config.TIMEZONE)
except Exception:  # sem tzdata (ex.: Windows sem o pacote): UTC-3 fixo
    _TZ = timezone(timedelta(hours=-3))


def now() -> datetime:
    return datetime.now(_TZ).replace(tzinfo=None)


def today() -> date:
    return now().date()
