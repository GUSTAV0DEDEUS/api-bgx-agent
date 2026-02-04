-- Migration: Tags e Leads
-- Data: 2026-02-03
-- Descrição: Adiciona tags JSONB em profiles/conversations,
--            campos de encerramento de conversas e tabela de leads com pipeline de vendas.

-- ============================================
-- 1. TAGS EM PROFILES (max 3 tags por cliente)
-- ============================================
ALTER TABLE profiles 
ADD COLUMN IF NOT EXISTS tags JSONB NOT NULL DEFAULT '[]'::jsonb;

-- Índice GIN para queries eficientes em tags
CREATE INDEX IF NOT EXISTS idx_profiles_tags ON profiles USING GIN (tags);

-- ============================================
-- 2. TAGS E ENCERRAMENTO EM CONVERSATIONS (max 5 tags por conversa)
-- ============================================
ALTER TABLE conversations 
ADD COLUMN IF NOT EXISTS tags JSONB NOT NULL DEFAULT '[]'::jsonb;

ALTER TABLE conversations 
ADD COLUMN IF NOT EXISTS closed_at TIMESTAMPTZ;

ALTER TABLE conversations 
ADD COLUMN IF NOT EXISTS closed_by VARCHAR(32);

ALTER TABLE conversations 
ADD COLUMN IF NOT EXISTS closed_reason TEXT;

-- Índice GIN para queries eficientes em tags
CREATE INDEX IF NOT EXISTS idx_conversations_tags ON conversations USING GIN (tags);

-- Índice para buscar conversas por status
CREATE INDEX IF NOT EXISTS idx_conversations_status ON conversations(status);

-- ============================================
-- 3. TABELA DE LEADS COM PIPELINE DE VENDAS
-- ============================================
CREATE TABLE IF NOT EXISTS leads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID UNIQUE NOT NULL REFERENCES conversations(id),
    profile_id UUID NOT NULL REFERENCES profiles(id),
    
    -- Dados comerciais do lead
    nome_cliente VARCHAR(255),
    nome_empresa VARCHAR(255),
    cargo VARCHAR(128),
    telefone VARCHAR(32),
    
    -- Qualificação
    tags JSONB NOT NULL DEFAULT '[]'::jsonb,
    score INTEGER DEFAULT 50 CHECK (score >= 0 AND score <= 100),
    notes TEXT,
    
    -- Status geral
    status VARCHAR(32) NOT NULL DEFAULT 'novo' CHECK (status IN ('novo', 'contatado', 'convertido', 'perdido')),
    
    -- Pipeline de vendas (checklist de steps)
    step_novo_lead BOOLEAN NOT NULL DEFAULT true,
    step_primeiro_contato BOOLEAN NOT NULL DEFAULT false,
    step_orcamento_realizado BOOLEAN NOT NULL DEFAULT false,
    step_orcamento_recusado BOOLEAN NOT NULL DEFAULT false,
    step_venda_convertida BOOLEAN NOT NULL DEFAULT false,
    
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

-- Índices para cada step do pipeline
CREATE INDEX IF NOT EXISTS idx_leads_step_novo_lead ON leads(step_novo_lead) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_leads_step_primeiro_contato ON leads(step_primeiro_contato) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_leads_step_orcamento_realizado ON leads(step_orcamento_realizado) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_leads_step_orcamento_recusado ON leads(step_orcamento_recusado) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_leads_step_venda_convertida ON leads(step_venda_convertida) WHERE deleted_at IS NULL;

-- Índice composto para score (leads quentes)
CREATE INDEX IF NOT EXISTS idx_leads_score ON leads(score DESC) WHERE deleted_at IS NULL;

-- ============================================
-- 4. TRIGGER PARA ATUALIZAR updated_at
-- ============================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger para leads
DROP TRIGGER IF EXISTS update_leads_updated_at ON leads;
CREATE TRIGGER update_leads_updated_at
    BEFORE UPDATE ON leads
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Trigger para profiles (se não existir)
DROP TRIGGER IF EXISTS update_profiles_updated_at ON profiles;
CREATE TRIGGER update_profiles_updated_at
    BEFORE UPDATE ON profiles
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Trigger para conversations (se não existir)
DROP TRIGGER IF EXISTS update_conversations_updated_at ON conversations;
CREATE TRIGGER update_conversations_updated_at
    BEFORE UPDATE ON conversations
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
