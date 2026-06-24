# Levantamento Geral do Sistema e Plano de Melhorias

Este documento apresenta o levantamento técnico do estado atual do sistema de inventário e propõe melhorias, com foco especial em segurança e boas práticas.

---

## 1. Estado Atual do Sistema (Levantamento)

O sistema de inventário está estruturado em uma arquitetura monolítica Flask no backend e HTML/CSS no frontend, utilizando SQLite como banco de dados.

### 1.1. Estrutura de Arquivos e Componentes
- **Backend (Python 3.10+, Flask, SQLite):**
  - `backend/app/__init__.py`: Inicialização do Flask, banco de dados (SQLAlchemy + Migrate) e controle de sesões e permissões em tempo real (`before_request`).
  - `backend/app/models.py`: Modelos de banco de dados (`User`, `Location`, `Sector`, `Equipment`, `AlmoxItem`, `Shelf`, `ShelfLevel`, etc.).
  - `backend/app/auth.py`: Fluxo de autenticação baseado em sessão com validação do hash de senhas (`werkzeug.security`).
  - `backend/app/routes/`: Blueprints isolados para cada módulo (`almoxarifado`, `api`, `equipments`, `locations`, `main`, `user`).
  - `backend/instance/app.db`: Banco de dados SQLite ativo (aprox. 112 KB).
- **Frontend (Vanilla CSS + HTML):**
  - `frontend/templates/`: Páginas organizadas por módulo (layouts, login, listas, formulários).
  - `frontend/static/styles.css`: Estilo customizado com suporte a modo escuro e tema "Obsidian Dark".
- **Deploy (Nginx + Gunicorn + Systemd):**
  - `deploy/nginx.conf`: Configuração do servidor reverso Nginx para o domínio `imoterraboa.solutecno.com.br`.
  - `deploy/inventario.service`: Serviço Systemd rodando Gunicorn na porta 5000 com o usuário `www-data`.
  - `deploy/setup.sh` e `deploy/setup_ssl.sh`: Scripts automatizados de instalação e setup de certificado SSL Let's Encrypt.

---

## 2. Auditoria e Diagnóstico de Segurança

Executamos o `security_scan.py` e verificamos o ambiente atual do servidor. Abaixo estão os pontos críticos e oportunidades de melhoria identificados:

### 2.1. Pontos Críticos e Vulnerabilidades
1. **Segredos Hardcoded:** A chave secreta do Flask (`SECRET_KEY`) está hardcoded no arquivo `backend/app/__init__.py` com o valor `"dev-secret-change-me"`.
2. **Cabeçalhos de Segurança Ausentes:** O arquivo de configuração `deploy/nginx.conf` não possui cabeçalhos básicos de segurança (como `X-Frame-Options`, `X-Content-Type-Options`, `Content-Security-Policy` e `XSS-Protection`).
3. **Falta de HTTPS Forçado como Padrão na Configuração:** Embora exista o script `setup_ssl.sh`, a configuração base de Nginx em `deploy/nginx.conf` define apenas a porta `80` (HTTP). O HTTPS só é ativado após a execução do Certbot.
4. **Ausência de Backups Automatizados:** Não há mecanismo para gerar e rotacionar backups periódicos do banco de dados SQLite (`app.db`), o que coloca os dados do inventário em risco caso ocorra falha de hardware ou erro no servidor.

---

## 3. Plano de Ação Recomendado (Mudanças Propostas)

Propomos a execução de melhorias de infraestrutura e código em 4 fases:

### Fase 1: Segurança da Configuração e Variáveis de Ambiente
- **Carregar SECRET_KEY do ambiente:** Modificar `backend/app/__init__.py` para carregar a chave via `os.environ.get("SECRET_KEY")` e definir um fallback seguro.
- **Configurar Variáveis no Systemd:** Atualizar `deploy/inventario.service` para incluir variáveis de ambiente (ex: `Environment="SECRET_KEY=sua-chave-secreta-producao"`).

### Fase 2: Fortalecimento do Nginx (Security Headers)
- **Cabeçalhos HTTP no Nginx:** Adicionar cabeçalhos de proteção ao `deploy/nginx.conf`:
  - `X-Frame-Options "SAMEORIGIN"` (evita Clickjacking)
  - `X-Content-Type-Options "nosniff"` (evita farejamento de MIME type)
  - `X-XSS-Protection "1; mode=block"` (filtro XSS legacy)
  - `Referrer-Policy "strict-origin-when-cross-origin"`

### Fase 3: Script de Backup do Banco de Dados
- **Backup de Banco de Dados:** Criar um script simples em `/var/www/inventario/deploy/backup_db.sh` para copiar o banco de dados `app.db` para um diretório seguro, com compressão (.gz) e carimbo de data/hora, e agendá-lo via Cron.

### Fase 4: UX - Filtragem Dinâmica de Setores por Localização
- **Filtro no Frontend (JavaScript):** Linkar os selects de "Localização" e "Setor" no cadastro, edição e filtros de busca de equipamentos para mostrar apenas setores válidos da localização selecionada.
