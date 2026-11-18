"""Request bodies. Numbers may arrive as JSON numbers or text such as ``"7,4"``."""

from __future__ import annotations

from typing import Optional, Union

from pydantic import BaseModel


class LoginIn(BaseModel):
    login: str = ""
    password: str = ""
    lang: Optional[str] = None


class LangIn(BaseModel):
    lang: str


class ClientIn(BaseModel):
    name: Optional[str] = None
    contact_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None


class PoolIn(BaseModel):
    name: Optional[str] = None
    volume_liters: Optional[Union[float, str]] = None
    environment: Optional[str] = None
