-- Migration: Adiciona step_negociacao ao pipeline de leads
-- Data: 2026-02-07
-- Descrição: Adiciona coluna step_negociacao entre step_primeiro_contato e step_orcamento_realizado

ALTER TABLE leads ADD COLUMN IF NOT EXISTS step_negociacao BOOLEAN NOT NULL DEFAULT FALSE;
