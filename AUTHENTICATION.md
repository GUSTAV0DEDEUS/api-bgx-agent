# Autenticação JWT - Guia de Uso

## Visão Geral

Este sistema implementa autenticação JWT (JSON Web Token) para proteger as rotas da API. Todos os usuários criados na V1 são tratados com permissões globais de admin, sem distinção de roles.

## Endpoints de Autenticação

### POST /auth/login

Endpoint para fazer login e obter um token JWT.

**Request:**
```json
{
  "username": "admin",
  "password": "admin123"
}
```

**Response (200 OK):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

**Erros:**
- `401 Unauthorized`: Credenciais inválidas
- `403 Forbidden`: Usuário inativo

### GET /auth/me

Retorna informações do usuário autenticado.

**Headers:**
```
Authorization: Bearer <seu_token_jwt>
```

**Response (200 OK):**
```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "username": "admin",
  "email": "admin@example.com",
  "is_active": true,
  "created_at": "2026-02-14T19:45:00Z"
}
```

**Erros:**
- `401 Unauthorized`: Token inválido ou expirado
- `403 Forbidden`: Usuário inativo

## Como Usar o Token JWT

### 1. Fazer Login

```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}'
```

### 2. Usar o Token

Inclua o token no header `Authorization` de todas as requisições protegidas:

```bash
curl -X GET http://localhost:8000/auth/me \
  -H "Authorization: Bearer seu_token_aqui"
```

## Como Proteger Rotas

Para proteger uma rota existente, adicione o parâmetro `current_user` com a dependência `get_current_user`:

```python
from typing import Annotated
from fastapi import Depends
from app.entities.user_entity import User
from app.middlewares.auth_middleware import get_current_user

@router.get("/leads")
def list_leads(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
):
    # Esta rota agora requer autenticação
    # O usuário autenticado está disponível em current_user
    ...
```

## Configuração

As seguintes variáveis de ambiente podem ser configuradas:

- `JWT_SECRET_KEY`: Chave secreta para assinar os tokens
  - **IMPORTANTE**: Altere esta chave em produção!
  - Se não configurada, o sistema gerará uma chave aleatória a cada reinício (tokens serão invalidados)
  - Este comportamento é intencional para desenvolvimento, forçando configuração adequada
  - Recomendação: Use uma string aleatória de 64+ caracteres
  - Exemplo: `openssl rand -hex 64`
- `JWT_ALGORITHM`: Algoritmo de criptografia (padrão: "HS256")
- `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`: Tempo de expiração do token em minutos (padrão: 43200 = 30 dias)

## Banco de Dados

### Migração

Execute o script SQL para criar a tabela de usuários:

```bash
psql -h localhost -U postgres -d agentic -f sql/007_users_authentication.sql
```

### Usuário Padrão

Um usuário admin é criado automaticamente na migração:

- **Username**: admin
- **Email**: admin@example.com
- **Password**: admin123

**IMPORTANTE**: Altere a senha padrão em produção!

## Segurança

### Boas Práticas

1. **Altere a JWT_SECRET_KEY**: Use uma chave forte e única em produção
2. **Use HTTPS**: Sempre use HTTPS em produção para proteger os tokens
3. **Rotação de Tokens**: Considere implementar refresh tokens para sessões longas
4. **Altere a Senha Padrão**: Altere a senha do usuário admin após a instalação
5. **Valide Requisições**: Sempre valide os dados de entrada nos endpoints

### Vulnerabilidades Conhecidas

- Tokens JWT não podem ser revogados até expirarem
- A senha padrão do admin é conhecida (deve ser alterada)

## Arquitetura

### Estrutura de Arquivos

```
app/
├── controllers/
│   └── auth_controller.py          # Endpoints de autenticação
├── dao/
│   └── user_dao.py                 # Acesso ao banco de dados de usuários
├── entities/
│   └── user_entity.py              # Modelo de dados do usuário
├── middlewares/
│   └── auth_middleware.py          # Middleware de autenticação
├── schemas/
│   └── auth_schemas.py             # Schemas Pydantic para autenticação
└── utils/
    └── auth.py                     # Utilitários JWT (hash, tokens)
sql/
└── 007_users_authentication.sql    # Migração do banco de dados
```

### Fluxo de Autenticação

1. Cliente envia credenciais para `/auth/login`
2. Servidor valida credenciais
3. Servidor gera token JWT assinado
4. Cliente armazena o token
5. Cliente inclui token em requisições protegidas
6. Middleware valida o token
7. Middleware carrega usuário do banco de dados
8. Requisição é processada com usuário autenticado

## Testes

Execute os testes de autenticação:

```bash
# Testes unitários
python /tmp/test_auth.py

# Testes de integração da API
python /tmp/test_auth_api.py
```

## Exemplo de Uso Completo

```python
import requests

# 1. Fazer login
response = requests.post(
    "http://localhost:8000/auth/login",
    json={"username": "admin", "password": "admin123"}
)
token = response.json()["access_token"]

# 2. Usar o token em requisições
headers = {"Authorization": f"Bearer {token}"}

# Ver informações do usuário
me = requests.get("http://localhost:8000/auth/me", headers=headers)
print(me.json())

# Acessar rota protegida
leads = requests.get("http://localhost:8000/leads", headers=headers)
print(leads.json())
```

## Suporte

Para dúvidas ou problemas, consulte:
- Documentação da API: http://localhost:8000/docs
- Código-fonte: `/app/controllers/auth_controller.py`
- Exemplos: `/app/controllers/example_protected_routes.py`
