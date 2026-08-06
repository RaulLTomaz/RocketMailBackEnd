from pydantic import BaseModel, ConfigDict, EmailStr, Field, HttpUrl

from app.schemas.post import PostResponse


class UsuarioBase(BaseModel):
    nome: str = Field(min_length=1, max_length=100)
    email: EmailStr


class UsuarioCreate(UsuarioBase):
    senha: str = Field(min_length=6, max_length=72)


class UsuarioOut(UsuarioBase):
    id: int
    foto_url: str | None = None
    model_config = ConfigDict(from_attributes=True)


class UsuarioUpdate(BaseModel):
    nome: str | None = Field(default=None, min_length=1, max_length=100)
    email: EmailStr | None = None
    senha: str | None = Field(default=None, min_length=6, max_length=72)
    # Alternativa ao multipart: URL absoluta já hospedada (ex.: CDN externa).
    foto_url: HttpUrl | None = None


class UsuarioSearchHit(BaseModel):
    usuario: UsuarioOut
    posts: list[PostResponse]
