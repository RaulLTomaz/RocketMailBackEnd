from pydantic import BaseModel, Field, field_validator, ConfigDict
from datetime import datetime

class PostBase(BaseModel):
    post: str = Field(..., min_length=1, max_length=280)

    @field_validator("post")
    def nao_aceita_so_espacos(cls, v):
        if not v.strip():
            raise ValueError("O conteúdo do post não pode ser vazio ou apenas espaços.")
        return v

class PostCreate(PostBase):
    pass

class UsuarioSimples(BaseModel):
    id: int
    nome: str

    model_config = ConfigDict(from_attributes=True)

class PostResponse(PostBase):
    id: int
    data_criacao: datetime
    usuario: UsuarioSimples

    model_config = ConfigDict(from_attributes=True)
