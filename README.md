# Sistema de Recomendação de Livros

Aplicação Streamlit para recomendar cinco livros usando TF-IDF e similaridade do cosseno.

## Arquivos

- `app.py`: interface e algoritmo de recomendação.
- `dados.csv`: catálogo de livros.
- `requirements.txt`: dependências Python.

## Executar localmente

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Publicar no Streamlit Community Cloud

1. Envie os três arquivos para um repositório GitHub.
2. Acesse https://share.streamlit.io/
3. Conecte sua conta GitHub.
4. Escolha o repositório e selecione `app.py` como arquivo principal.
5. Publique a aplicação.

## Configurar o Google Sheets

A aplicação espera credenciais de uma conta de serviço nos Secrets do Streamlit.

1. Crie um projeto no Google Cloud e habilite Google Sheets API e Google Drive API.
2. Crie uma conta de serviço e gere uma chave JSON.
3. Crie uma planilha Google Sheets e compartilhe-a com o e-mail da conta de serviço como Editor.
4. Copie o ID da planilha, que aparece na URL entre `/d/` e `/edit`.
5. No Streamlit Cloud, abra as configurações da aplicação e adicione os Secrets:

```toml
[gcp_service_account]
type = "service_account"
project_id = "SEU_PROJECT_ID"
private_key_id = "SUA_PRIVATE_KEY_ID"
private_key = "-----BEGIN PRIVATE KEY-----\\nSUA_CHAVE\\n-----END PRIVATE KEY-----\\n"
client_email = "EMAIL_DA_CONTA_DE_SERVICO"
client_id = "SEU_CLIENT_ID"
token_uri = "https://oauth2.googleapis.com/token"

[google_sheets]
spreadsheet_id = "ID_DA_PLANILHA"
worksheet_name = "Avaliacoes"
```

Não envie credenciais ou chaves JSON ao GitHub. A aplicação cria a aba `Avaliacoes` se ela ainda não existir.

## Observações

- O catálogo utilizado precisa estar na mesma pasta de `app.py` e chamar-se `dados.csv`.
- A aplicação considera apenas livros com sinopse preenchida.
- A busca por título mostra até 30 correspondências para seleção.
- A busca por sinopse livre usa o mesmo vocabulário TF-IDF treinado no catálogo.
- Apenas avaliações explicitamente marcadas como gostei/não gostei são enviadas.
