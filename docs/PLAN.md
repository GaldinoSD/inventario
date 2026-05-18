# Plano de Refatoração e Melhorias do Inventário

Este plano foi criado pelo **project-planner** após a análise inicial (Phase 1) do sistema de inventário para a igreja.

## 1. Visão Geral do Sistema Atual
O projeto atual é uma aplicação monolítica em Flask + SQLite que atende aos requisitos básicos:
- Cadastros de Localizações, Setores e Equipamentos.
- Upload de Notas Fiscais.
- Módulo de Almoxarifado para movimentação de estoque.
- Leitura de código de barras (PAT) via câmera (frontend em HTML5).

**Principais Problemas Encontrados:**
1. **Segurança Crítica:** A autenticação em `app/auth.py` utiliza credenciais "hardcoded" (`admin` / `1234`). Não há tabela de usuários nem senhas com hash no banco de dados.
2. **Manutenibilidade (God Object):** O arquivo `app/routes.py` concentra toda a lógica da aplicação (quase 900 linhas), misturando todas as entidades do sistema.
3. **Gerenciamento do Banco de Dados:** Não há sistema de migrações estruturado configurado (ex: Alembic/Flask-Migrate), o que dificulta a evolução do esquema do banco de dados sem perda de dados.
4. **Regras de Negócio Incompletas:** Os equipamentos não possuem um campo de **Status** claro (ex: "Ativo", "Em Manutenção", "Baixado/Doado"), o que é vital num inventário de longo prazo.

---

## 2. Mudanças Propostas

> [!IMPORTANT]
> A refatoração será dividida em módulos para não quebrar funcionalidades existentes, isolando a lógica e garantindo a escalabilidade do sistema.

### Fase A: Fundação e Segurança (security-auditor & database-architect)
- **Tabela de Usuários:** Criar o modelo `User` em `models.py` com `id`, `username`, `password_hash` e `role` (Admin, Viewer).
- **Refatorar Autenticação:** Atualizar `auth.py` para usar `werkzeug.security.check_password_hash`. Remover as credenciais fixas no código.
- **Migrações:** Inicializar o `Flask-Migrate` para versionar o banco de dados.
- **Melhoria no Equipment:** Adicionar o campo `status` ao modelo `Equipment`.

### Fase B: Refatoração da Arquitetura Core (backend-specialist)
- **Blueprints:** Dividir o gigantesco `routes.py` em múltiplos arquivos dentro de `app/routes/`:
  - `auth_routes.py`
  - `locations_routes.py`
  - `equipments_routes.py`
  - `almoxarifado_routes.py`
  - `api_routes.py`
- **Registro no App:** Refatorar `app/__init__.py` para registrar todos os novos blueprints dinamicamente.

### Fase C: UX e Polimento (frontend-specialist & test-engineer)
- **Frontend Ajustes:** Melhorar a indicação visual do `status` do equipamento nas listas e na interface de leitura do scanner (`scan.html`).
- **Feedback Visual:** Implementar confirmações mais robustas com JS/SweetAlert ao excluir itens.
- **Testes Manuais/Scripts:** Criar rotina de pre-flight checks (baseado no `checklist.py`) antes de dar a refatoração como concluída.

---

## 3. Plano de Verificação

### Testes a serem aplicados:
- **Testes de Rota:** Garantir que todas as rotas (que agora estarão em blueprints diferentes) resolvam com status 200 OK e não quebrem a sessão.
- **Validação de Login:** Testar o login falho, bem-sucedido e bloqueio de rotas para usuários não autenticados.
- **Integração de Uploads:** Validar se upload e exclusão física das NFs (`invoice_file`) continua funcionando após separar o arquivo `equipments_routes.py`.
