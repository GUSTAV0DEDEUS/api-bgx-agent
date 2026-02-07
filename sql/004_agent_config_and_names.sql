-- Migration: Agent Config, Nome separado em profiles, Status corrigido em leads
-- Data: 2026-02-07
-- Descrição:
--   1. Substitui display_name em profiles por first_name + last_name
--   2. Corrige CHECK de status em leads (alinha SQL com entity) + adiciona em_negociacao
--   3. Cria tabela agent_config (singleton, futuro multi-tenant)

-- ============================================
-- 1. PROFILES: display_name → first_name + last_name
-- ============================================
ALTER TABLE profiles ADD COLUMN IF NOT EXISTS first_name VARCHAR(128);
ALTER TABLE profiles ADD COLUMN IF NOT EXISTS last_name VARCHAR(128);
ALTER TABLE profiles DROP COLUMN IF EXISTS display_name;

-- ============================================
-- 2. LEADS: Corrigir CHECK de status
--    SQL antigo: ('novo', 'contatado', 'convertido', 'perdido')
--    Entity usa: novo, em_contato, em_negociacao, proposta_enviada, fechado, perdido
-- ============================================
ALTER TABLE leads DROP CONSTRAINT IF EXISTS leads_status_check;
ALTER TABLE leads ADD CONSTRAINT leads_status_check
    CHECK (status IN ('novo', 'em_contato', 'em_negociacao', 'proposta_enviada', 'fechado', 'perdido'));

-- ============================================
-- 3. TABELA AGENT_CONFIG (singleton global)
-- ============================================
CREATE TABLE IF NOT EXISTS agent_config (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Tom do agente
    tone VARCHAR(32) NOT NULL DEFAULT 'profissional'
        CHECK (tone IN ('profissional', 'descontraido', 'tecnico', 'amigavel')),

    -- Uso de emojis
    use_emojis VARCHAR(32) NOT NULL DEFAULT 'moderado'
        CHECK (use_emojis IN ('sempre', 'moderado', 'nunca')),

    -- Estilo de resposta
    response_style VARCHAR(32) NOT NULL DEFAULT 'conversacional'
        CHECK (response_style IN ('formal', 'conversacional', 'consultivo', 'direto')),

    -- Estilo de saudação
    greeting_style VARCHAR(32) NOT NULL DEFAULT 'caloroso'
        CHECK (greeting_style IN ('caloroso', 'neutro', 'objetivo')),

    -- Tamanho máximo de cada chunk de mensagem (para split)
    max_message_length INTEGER NOT NULL DEFAULT 300
        CHECK (max_message_length >= 50 AND max_message_length <= 1000),

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Trigger para updated_at
DROP TRIGGER IF EXISTS update_agent_config_updated_at ON agent_config;
CREATE TRIGGER update_agent_config_updated_at
    BEFORE UPDATE ON agent_config FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Seed: registro singleton com defaults
INSERT INTO agent_config (tone, use_emojis, response_style, greeting_style, max_message_length)
SELECT 'profissional', 'moderado', 'conversacional', 'caloroso', 300
WHERE NOT EXISTS (SELECT 1 FROM agent_config LIMIT 1);
