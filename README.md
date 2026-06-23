# Inventário de Equipamentos (Igrejas) — Flask + SQLite

Sistema inicial com:
- Cadastro de **Localizações/Igrejas**
- Cadastro de **Setores**
- Cadastro de **Equipamentos** (seleciona setor e localização já cadastrados)
- **Pesquisa por PAT/Código de barras**, com opção de **leitura via câmera** (HTML5)

## Requisitos
- Python 3.10+ (recomendado)
- pip

## Como rodar (Windows / Linux)
1) Navegue para a pasta backend:
```bash
cd backend
```

2) Crie e ative um virtualenv:
```bash
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate
```

3) Instale dependências:
```bash
pip install -r requirements.txt
```

4) Rode o servidor:
```bash
python run.py
```

Abra: http://127.0.0.1:5000

## Primeira execução (seed)
Na primeira execução, o sistema cria o banco `backend/instance/app.db` e
pré-cadastra os setores padrão: Ministério de Louvor, Administrativo, Mídia, Geral.

## Estrutura
- `backend/` códigos e banco de dados do Backend
- `frontend/` páginas e estilos do Frontend

## Observações
- `barcode_pat` (PAT/código) é **único** por equipamento.
- Exclusão de Setor/Localização com equipamentos vinculados é bloqueada (com mensagem).
