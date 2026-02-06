-- Migration: Human Takeover e Status de Lead
-- Data: 2026-02-06
-- Descrição: Adiciona status "human" para conversas onde consultor assume,
--            e melhora os status do lead para refletir pipeline de orçamento.

-- ============================================
-- 1. ATUALIZAR STATUS DA CONVERSATION
-- ============================================
-- Remove constraint antiga e adiciona nova com status "human"
ALTER TABLE conversations 
DROP CONSTRAINT IF EXISTS conversations_status_check;

ALTER TABLE conversations 
ADD CONSTRAINT conversations_status_check 
CHECK (status IN ('open', 'human', 'closed'));

-- ============================================
-- 2. ATUALIZAR STATUS DO LEAD
-- ============================================
-- Novos status:
--   novo: Lead recém criado
--   em_contato: Em processo de qualificação
--   proposta_enviada: Orçamento/proposta foi enviado
--   fechado: Venda realizada com sucesso
--   perdido: Cliente desistiu ou recusou

-- Primeiro, atualiza os dados existentes para os novos valores
UPDATE leads SET status = 'em_contato' WHERE status = 'contatado';
UPDATE leads SET status = 'fechado' WHERE status = 'convertido';

-- Remove constraint antiga
ALTER TABLE leads 
DROP CONSTRAINT IF EXISTS leads_status_check;

-- Adiciona nova constraint com status atualizados
ALTER TABLE leads 
ADD CONSTRAINT leads_status_check 
CHECK (status IN ('novo', 'em_contato', 'proposta_enviada', 'fechado', 'perdido'));

-- ============================================
-- 3. ADICIONAR STEP ORÇAMENTO ACEITO
-- ============================================
ALTER TABLE leads
ADD COLUMN IF NOT EXISTS step_orcamento_aceito BOOLEAN NOT NULL DEFAULT false;

-- Índice para o novo step
CREATE INDEX IF NOT EXISTS idx_leads_step_orcamento_aceito 
ON leads(step_orcamento_aceito) WHERE deleted_at IS NULL;

-- ============================================
-- 4. COMENTÁRIOS PARA DOCUMENTAÇÃO
-- ============================================
COMMENT ON COLUMN conversations.status IS 'Status da conversa: open (IA responde), human (consultor responde), closed (encerrada)';
COMMENT ON COLUMN leads.status IS 'Status do lead: novo, em_contato, proposta_enviada, fechado, perdido';
COMMENT ON COLUMN leads.step_orcamento_aceito IS 'Cliente aceitou o orçamento/proposta';
