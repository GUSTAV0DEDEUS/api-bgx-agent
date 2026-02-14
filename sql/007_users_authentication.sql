-- ============================================================
-- Migration 007: Users and Authentication
-- Data: 2026-02-14
-- Descrição: Adiciona tabela de usuários para autenticação JWT
--            Todos os usuários terão permissões de admin (V1)
-- ============================================================

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================================
-- USERS TABLE
-- ============================================================

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(128) NOT NULL UNIQUE,
    email VARCHAR(255) NOT NULL UNIQUE,
    hashed_password VARCHAR(255) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_is_active ON users(is_active);

COMMENT ON TABLE users IS 'Usuários do sistema com autenticação JWT. Todos têm permissões de admin (V1)';

-- ============================================================
-- TRIGGER (updated_at automático)
-- ============================================================

DROP TRIGGER IF EXISTS update_users_updated_at ON users;
CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================
-- SEED (usuário admin padrão)
-- ============================================================

-- Senha padrão: admin123
-- Hash gerado com bcrypt
INSERT INTO users (username, email, hashed_password)
SELECT 'admin', 'admin@example.com', '$2b$12$W1SeAGq2.jrSK9g9Vcr9r.dzuyOI9UWGGWfIViYsJdnqi6otdTbC.'
WHERE NOT EXISTS (SELECT 1 FROM users WHERE username = 'admin');

COMMENT ON COLUMN users.hashed_password IS 'Senha hasheada com bcrypt. Senha padrão do admin: admin123';
