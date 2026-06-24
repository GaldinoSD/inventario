#!/bin/bash

# Script de Configuração de Deploy - Sistema de Inventário
# Executar este script com privilégios sudo: sudo ./setup.sh

set -e

# Cores para output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # Sem Cor

echo -e "${BLUE}=== Iniciando Configuração de Deploy do Inventário ===${NC}"

# 1. Verificar se é executado como root (ou sudo)
if [ "$EUID" -ne 0 ]; then
  echo -e "${RED}Erro: Por favor, execute este script como root ou usando sudo.${NC}"
  exit 1
fi

# 2. Atualizar pacotes e instalar Nginx se necessário
echo -e "${YELLOW}[1/6] Verificando e instalando dependências do sistema...${NC}"
apt update
apt install -y nginx curl python3-pip python3-venv

# 3. Atualizar dependências do Python (instalando Gunicorn)
echo -e "${YELLOW}[2/6] Atualizando dependências da aplicação no ambiente virtual...${NC}"
if [ -d "/var/www/inventario/venv" ] && [ -f "/var/www/inventario/venv/bin/pip" ]; then
    /var/www/inventario/venv/bin/pip install -r /var/www/inventario/backend/requirements.txt
else
    echo -e "${YELLOW}Criando/Recriando ambiente virtual (venv) compatível com Linux...${NC}"
    rm -rf /var/www/inventario/venv
    python3 -m venv /var/www/inventario/venv
    /var/www/inventario/venv/bin/pip install --upgrade pip
    /var/www/inventario/venv/bin/pip install -r /var/www/inventario/backend/requirements.txt
fi

# 4. Ajustar permissões para o SQLite
echo -e "${YELLOW}[3/6] Ajustando permissões da pasta instance e do banco de dados...${NC}"
# Garante que a pasta instance e o banco de dados pertençam ao grupo www-data
mkdir -p /var/www/inventario/backend/instance
chown -R www-data:www-data /var/www/inventario/backend/instance
chmod -R 775 /var/www/inventario/backend/instance
if [ -f "/var/www/inventario/backend/instance/app.db" ]; then
    chown www-data:www-data /var/www/inventario/backend/instance/app.db
    chmod 664 /var/www/inventario/backend/instance/app.db
fi

# Cria arquivos de log para o Gunicorn e define permissões
touch /var/log/gunicorn-access.log /var/log/gunicorn-error.log
chown www-data:www-data /var/log/gunicorn-access.log /var/log/gunicorn-error.log
chmod 664 /var/log/gunicorn-access.log /var/log/gunicorn-error.log

# 5. Configurar o Systemd Service
echo -e "${YELLOW}[4/6] Configurando o serviço Systemd (Gunicorn)...${NC}"
cp /var/www/inventario/deploy/inventario.service /etc/systemd/system/inventario.service

# Recarregar daemon, iniciar e habilitar o serviço
systemctl daemon-reload
systemctl enable inventario.service
systemctl restart inventario.service

# Verificar se o serviço iniciou com sucesso
if systemctl is-active --quiet inventario.service; then
    echo -e "${GREEN}Serviço inventario.service está rodando com sucesso!${NC}"
else
    echo -e "${RED}Erro: O serviço inventario.service falhou ao iniciar. Verifique com: journalctl -u inventario.service${NC}"
    exit 1
fi

# 6. Configurar o Nginx
echo -e "${YELLOW}[5/6] Configurando o servidor web Nginx...${NC}"
cp /var/www/inventario/deploy/nginx.conf /etc/nginx/sites-available/inventario

# Criar link simbólico para habilitar o site
ln -sf /etc/nginx/sites-available/inventario /etc/nginx/sites-enabled/inventario

# Remover a configuração padrão do Nginx se existir para evitar conflitos de portas
if [ -f "/etc/nginx/sites-enabled/default" ]; then
    echo -e "${YELLOW}Desativando o site padrão (default) do Nginx para evitar conflitos...${NC}"
    rm /etc/nginx/sites-enabled/default
fi

# Testar e recarregar o Nginx
nginx -t
systemctl restart nginx

# 7. Configurar Firewall se UFW estiver ativo
echo -e "${YELLOW}[6/6] Ajustando regras de firewall (se ativo)...${NC}"
if command -v ufw >/dev/null; then
    ufw allow 'Nginx Full' || true
fi

echo -e "${GREEN}=== Configuração concluída com sucesso! ===${NC}"
echo -e "A aplicação já está online e disponível no IP público desta VPS."
echo -e "Para verificar o status do processo da aplicação, use: ${BLUE}systemctl status inventario.service${NC}"
echo -e "Para ver os logs em tempo real, use: ${BLUE}journalctl -u inventario.service -f${NC}"
echo -e ""
echo -e "${YELLOW}Dica para apontamento de domínio posterior:${NC}"
echo -e "1. Edite o arquivo ${BLUE}/etc/nginx/sites-available/inventario${NC} e altere o ${BLUE}server_name _${NC} para ${BLUE}server_name seu-dominio.com${NC}."
echo -e "2. Reinicie o Nginx: ${BLUE}sudo systemctl restart nginx${NC}"
echo -e "3. Instale o Certbot para SSL gratuito: ${BLUE}sudo apt install certbot python3-certbot-nginx && sudo certbot --nginx -d seu-dominio.com${NC}"
