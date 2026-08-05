"""Tabelas SQLAlchemy Core — importe este pacote para registrar no MetaData."""

from .like import like
from .post import post
from .seguir import seguir
from .usuario import usuario

__all__ = ["usuario", "post", "seguir", "like"]
