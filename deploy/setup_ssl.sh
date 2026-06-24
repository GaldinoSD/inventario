#!/bin/bash

# Script de Configuração de SSL - Sistema de Inventário
# Executar este script com privilégios sudo: sudo ./setup_ssl.sh

set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

DOMAIN="imoterraboa.solutecno.com.br"

echo -e "${BLUE}=== Iniciando Configuração de SSL para $DOMAIN ===${NC}"

# 1. Verificar privilégios de root
if [ "$EUID" -ne 0 ]; then
  echo -e "${RED}Erro: Por favor, execute este script como root ou usando sudo.${NC}"
  exit 1
fi

# 2. Instalar Certbot se necessário
echo -e "${YELLOW}[1/4] Instalando Certbot e dependências...${NC}"
apt update
apt install -y certbot python3-certbot-nginx

# 3. Atualizar configuração do Nginx com o novo domínio
echo -e "${YELLOW}[2/4] Atualizando arquivo de configuração do Nginx...${NC}"
cp /var/www/inventario/deploy/nginx.conf /etc/nginx/sites-available/inventario

# Testar e recarregar Nginx
nginx -t
systemctl reload nginx

# 4. Solicitar o Certificado SSL via Certbot
echo -e "${YELLOW}[3/4] Solicitando certificado SSL para $DOMAIN via Let's Encrypt...${NC}"
echo -e "${YELLOW}Isso pode demorar um momento enquanto o Let's Encrypt valida o domínio...${NC}"

# Executa o certbot de forma não interativa, aceitando os termos e configurando o redirecionamento HTTP para HTTPS
certbot --nginx -d $DOMAIN --non-interactive --agree-tos --register-unsafely-without-email --redirect

# 5. Reiniciar Nginx para garantir que todas as alterações de SSL foram aplicadas
echo -e "${YELLOW}[4/4] Reiniciando Nginx...${NC}"
systemctl restart nginx

echo -e "${GREEN}=== Certificado SSL configurado com sucesso para https://$DOMAIN ===${NC}"
echo -e "Agora a aplicação é acessada de forma segura através do domínio."
echo -e "O Certbot configurou a renovação automática semanal do certificado no cron/systemd timers do sistema."
