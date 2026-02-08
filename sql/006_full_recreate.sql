-- ============================================================
-- Migration 006: Schema completo final (recreate from scratch)
-- Data: 2026-02-07
-- Descrição: Script unificado com todas as tabelas, índices,
--            triggers e seed. Seguro para executar em banco limpo
--            (usa IF NOT EXISTS em tudo).
-- ============================================================

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================================
-- 1. PROFILES
-- ============================================================

CREATE TABLE IF NOT EXISTS profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    whatsapp_number VARCHAR(32) NOT NULL UNIQUE,
    first_name VARCHAR(128),
    last_name VARCHAR(128),
    tags JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_profiles_tags ON profiles USING GIN (tags);

-- ============================================================
-- 2. CONVERSATIONS
-- ============================================================

CREATE TABLE IF NOT EXISTS conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id UUID NOT NULL REFERENCES profiles(id),
    status VARCHAR(32) NOT NULL DEFAULT 'open'
        CHECK (status IN ('open', 'human', 'closed')),
    tags JSONB NOT NULL DEFAULT '[]'::jsonb,
    closed_at TIMESTAMPTZ,
    closed_by VARCHAR(32),
    closed_reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_conversations_profile_id ON conversations(profile_id);
CREATE INDEX IF NOT EXISTS idx_conversations_status ON conversations(status);
CREATE INDEX IF NOT EXISTS idx_conversations_tags ON conversations USING GIN (tags);

COMMENT ON COLUMN conversations.status IS 'open (IA responde), human (consultor responde), closed (encerrada)';

-- ============================================================
-- 3. MESSAGES
-- ============================================================

CREATE TABLE IF NOT EXISTS messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES conversations(id),
    profile_id UUID NOT NULL REFERENCES profiles(id),
    role VARCHAR(16) NOT NULL CHECK (role IN ('user', 'agent', 'admin')),
    message_type VARCHAR(32) NOT NULL DEFAULT 'text',
    content TEXT NOT NULL,
    provider_message_id VARCHAR(128),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_messages_conversation_id ON messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_messages_profile_id ON messages(profile_id);

-- ============================================================
-- 4. LEADS  (temperatura: quente / morno / frio)
-- ============================================================

CREATE TABLE IF NOT EXISTS leads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID UNIQUE NOT NULL REFERENCES conversations(id),
    profile_id UUID NOT NULL REFERENCES profiles(id),

    -- Dados comerciais
    nome_cliente VARCHAR(255),
    nome_empresa VARCHAR(255),
    cargo VARCHAR(128),
    telefone VARCHAR(32),

    -- Qualificação
    tags JSONB NOT NULL DEFAULT '[]'::jsonb,
    score INTEGER DEFAULT NULL CHECK (score IS NULL OR (score >= 0 AND score <= 100)),
    notes TEXT,

    -- Temperatura do lead (definida pela IA na fase de negociação)
    status VARCHAR(32) NOT NULL DEFAULT 'morno'
        CHECK (status IN ('quente', 'morno', 'frio')),

    -- Pipeline de vendas (checklist de steps)
    step_novo_lead          BOOLEAN NOT NULL DEFAULT true,
    step_primeiro_contato   BOOLEAN NOT NULL DEFAULT true,
    step_negociacao         BOOLEAN NOT NULL DEFAULT false,
    step_orcamento_realizado BOOLEAN NOT NULL DEFAULT false,
    step_orcamento_aceito   BOOLEAN NOT NULL DEFAULT false,
    step_orcamento_recusado BOOLEAN NOT NULL DEFAULT false,
    step_venda_convertida   BOOLEAN NOT NULL DEFAULT false,
    step_venda_perdida      BOOLEAN NOT NULL DEFAULT false,

    -- Soft delete
    deleted_at TIMESTAMPTZ,

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Índices para leads
CREATE INDEX IF NOT EXISTS idx_leads_profile_id ON leads(profile_id);
CREATE INDEX IF NOT EXISTS idx_leads_status ON leads(status);
CREATE INDEX IF NOT EXISTS idx_leads_deleted_at ON leads(deleted_at) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_leads_tags ON leads USING GIN (tags);
CREATE INDEX IF NOT EXISTS idx_leads_score ON leads(score DESC) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_leads_step_novo_lead ON leads(step_novo_lead) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_leads_step_primeiro_contato ON leads(step_primeiro_contato) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_leads_step_negociacao ON leads(step_negociacao) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_leads_step_orcamento_realizado ON leads(step_orcamento_realizado) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_leads_step_orcamento_aceito ON leads(step_orcamento_aceito) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_leads_step_orcamento_recusado ON leads(step_orcamento_recusado) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_leads_step_venda_convertida ON leads(step_venda_convertida) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_leads_step_venda_perdida ON leads(step_venda_perdida) WHERE deleted_at IS NULL;

COMMENT ON COLUMN leads.status IS 'Temperatura: quente (score>=70), morno (40-69), frio (<40)';
COMMENT ON COLUMN leads.score IS 'Score de qualificação (0-100). NULL até fase de negociação.';
COMMENT ON COLUMN leads.step_venda_perdida IS 'Venda perdida / cliente desistiu';

-- ============================================================
-- 5. AGENT CONFIG  (singleton global)
-- ============================================================

CREATE TABLE IF NOT EXISTS agent_config (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tone VARCHAR(32) NOT NULL DEFAULT 'profissional'
        CHECK (tone IN ('profissional', 'descontraido', 'tecnico', 'amigavel')),
    use_emojis VARCHAR(32) NOT NULL DEFAULT 'moderado'
        CHECK (use_emojis IN ('sempre', 'moderado', 'nunca')),
    response_style VARCHAR(32) NOT NULL DEFAULT 'conversacional'
        CHECK (response_style IN ('formal', 'conversacional', 'consultivo', 'direto')),
    greeting_style VARCHAR(32) NOT NULL DEFAULT 'caloroso'
        CHECK (greeting_style IN ('caloroso', 'neutro', 'objetivo')),
    max_message_length INTEGER NOT NULL DEFAULT 300
        CHECK (max_message_length >= 50 AND max_message_length <= 1000),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- 6. TRIGGERS  (updated_at automático)
-- ============================================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE 'plpgsql';

DROP TRIGGER IF EXISTS update_profiles_updated_at ON profiles;
CREATE TRIGGER update_profiles_updated_at
    BEFORE UPDATE ON profiles FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_conversations_updated_at ON conversations;
CREATE TRIGGER update_conversations_updated_at
    BEFORE UPDATE ON conversations FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_messages_updated_at ON messages;
CREATE TRIGGER update_messages_updated_at
    BEFORE UPDATE ON messages FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_leads_updated_at ON leads;
CREATE TRIGGER update_leads_updated_at
    BEFORE UPDATE ON leads FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_agent_config_updated_at ON agent_config;
CREATE TRIGGER update_agent_config_updated_at
    BEFORE UPDATE ON agent_config FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================
-- 7. SEED  (agent_config singleton)
-- ============================================================

INSERT INTO agent_config (tone, use_emojis, response_style, greeting_style, max_message_length)
SELECT 'profissional', 'moderado', 'conversacional', 'caloroso', 300
WHERE NOT EXISTS (SELECT 1 FROM agent_config LIMIT 1);
