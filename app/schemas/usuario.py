from pydantic import BaseModel, EmailStr, ConfigDict, Field


class UsuarioBase(BaseModel):
    nome: str = Field(min_length=1, max_length=100)
    email: EmailStr


class UsuarioCreate(UsuarioBase):
    senha: str = Field(min_length=6, max_length=72)


class UsuarioOut(UsuarioBase):
    id: int
    model_config = ConfigDict(from_attributes=True)


class UsuarioUpdate(BaseModel):
    nome: str | None = Field(default=None, min_length=1, max_length=100)
    email: EmailStr | None = None
    senha: str | None = Field(default=None, min_length=6, max_length=72)
