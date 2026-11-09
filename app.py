import streamlit as st
import pandas as pd
import numpy as np
import re
from pathlib import Path
from datetime import datetime, timezone
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import linear_kernel

# ---------------------------------------------------------
# CONFIGURAÇÕES GERAIS
# ---------------------------------------------------------
st.set_page_config(
    page_title="Recomendador de Livros",
    page_icon="📚",
    layout="wide"
)

CAMINHO_DADOS = Path(__file__).parent / "dados.csv"
QUANTIDADE_RECOMENDACOES = 5


# ---------------------------------------------------------
# CARREGAMENTO E PREPARAÇÃO DOS DADOS
# ---------------------------------------------------------
@st.cache_data
def carregar_livros(caminho):
    dados = pd.read_csv(caminho, encoding="utf-8")

    colunas_necessarias = ["titulo", "autor", "descricao"]
    for coluna in colunas_necessarias:
        if coluna not in dados.columns:
            raise ValueError(f"A coluna obrigatória '{coluna}' não foi encontrada.")

    # Corrige aspas tipográficas que vieram como caracteres de controle
    # (por exemplo, U+0093 e U+0094) em algumas descrições do CSV.
    def limpar_texto(texto):
        texto = str(texto)
        texto = texto.replace("\u0091", "‘").replace("\u0092", "’")
        texto = texto.replace("\u0093", "“").replace("\u0094", "”")
        texto = texto.replace("\u0096", "–").replace("\u0097", "—")
        # Remove caracteres de controle invisíveis ou não imprimíveis,
        # preservando tabulações e quebras de linha.
        texto = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]", "", texto)
        return texto.strip()

    dados["descricao"] = (
        dados["descricao"].fillna("").astype(str).map(limpar_texto)
    )
    dados["titulo"] = dados["titulo"].fillna("Título não informado").astype(str).map(limpar_texto)
    dados["autor"] = dados["autor"].fillna("Autor não informado").astype(str).map(limpar_texto)
    dados["titulo"] = dados["titulo"].fillna("Título não informado").astype(str)
    dados["autor"] = dados["autor"].fillna("Autor não informado").astype(str)

    # O modelo textual precisa de uma sinopse não vazia.
    dados = dados[dados["descricao"] != ""].copy()
    dados = dados.reset_index(drop=True)

    if "genero" not in dados.columns:
        dados["genero"] = ""

    return dados


@st.cache_resource
def treinar_modelo(textos):
    # Configuração unigram usada nos testes do projeto.
    vetorizador = TfidfVectorizer(
        lowercase=True,
        stop_words=None,
        ngram_range=(1, 1),
        min_df=2,
        max_features=30000
    )
    matriz = vetorizador.fit_transform(textos)
    return vetorizador, matriz


# ---------------------------------------------------------
# FUNÇÕES DE RECOMENDAÇÃO
# ---------------------------------------------------------
def recomendar_por_livro(indice_livro, matriz, dados, quantidade=5):
    similaridades = linear_kernel(
        matriz[indice_livro], matriz
    ).flatten()

    indices = similaridades.argsort()[::-1]
    indices = [i for i in indices if i != indice_livro][:quantidade]

    resultado = dados.iloc[indices].copy()
    resultado["similaridade"] = similaridades[indices]
    return resultado


def recomendar_por_texto(texto, vetorizador, matriz, dados, quantidade=5):
    vetor_consulta = vetorizador.transform([texto])

    if vetor_consulta.nnz == 0:
        return pd.DataFrame()

    similaridades = linear_kernel(
        vetor_consulta, matriz
    ).flatten()

    indices = similaridades.argsort()[::-1][:quantidade]

    resultado = dados.iloc[indices].copy()
    resultado["similaridade"] = similaridades[indices]
    return resultado


# ---------------------------------------------------------
# REGISTRO DAS AVALIAÇÕES NO GOOGLE SHEETS
# ---------------------------------------------------------
def registrar_avaliacoes_google_sheets(registros):
    """
    Para ativar esta função, configure os Secrets do Streamlit:

    [gcp_service_account]
    type = "service_account"
    project_id = "..."
    private_key_id = "..."
    private_key = "-----BEGIN PRIVATE KEY-----\\n...\\n-----END PRIVATE KEY-----\\n"
    client_email = "..."
    client_id = "..."
    token_uri = "https://oauth2.googleapis.com/token"

    [google_sheets]
    spreadsheet_id = "ID_DA_PLANILHA"
    worksheet_name = "Avaliacoes"
    """
    try:
        import gspread
        from google.oauth2.service_account import Credentials

        if "gcp_service_account" not in st.secrets:
            return False, (
                "A integração com o Google Sheets ainda não foi configurada. "
                "As avaliações não foram enviadas."
            )

        conta = dict(st.secrets["gcp_service_account"])
        escopos = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        credenciais = Credentials.from_service_account_info(
            conta, scopes=escopos
        )
        cliente = gspread.authorize(credenciais)

        configuracao = st.secrets.get("google_sheets", {})
        spreadsheet_id = configuracao.get("spreadsheet_id")
        nome_aba = configuracao.get("worksheet_name", "Avaliacoes")

        if not spreadsheet_id:
            return False, "O ID da planilha não foi configurado nos Secrets."

        planilha = cliente.open_by_key(spreadsheet_id)

        try:
            aba = planilha.worksheet(nome_aba)
        except gspread.WorksheetNotFound:
            aba = planilha.add_worksheet(
                title=nome_aba, rows=1000, cols=12
            )

        cabecalho = [
            "data_hora_utc",
            "tipo_pesquisa",
            "consulta",
            "titulo_base",
            "titulo_recomendado",
            "autor_recomendado",
            "genero_recomendado",
            "similaridade",
            "avaliacao"
        ]

        if not aba.get_all_values():
            aba.append_row(cabecalho)

        linhas = []
        for registro in registros:
            linhas.append([
                registro["data_hora_utc"],
                registro["tipo_pesquisa"],
                registro["consulta"],
                registro["titulo_base"],
                registro["titulo_recomendado"],
                registro["autor_recomendado"],
                registro["genero_recomendado"],
                registro["similaridade"],
                registro["avaliacao"]
            ])

        if linhas:
            aba.append_rows(linhas, value_input_option="USER_ENTERED")

        return True, f"{len(linhas)} avaliação(ões) registrada(s) com sucesso."

    except Exception as erro:
        return False, f"Não foi possível registrar as avaliações: {erro}"


# ---------------------------------------------------------
# INICIALIZAÇÃO
# ---------------------------------------------------------
st.title("📚 Sistema de Recomendação de Livros")
st.write(
    "Encontre livros semelhantes a uma obra que você gostou "
    "ou descubra sugestões a partir de uma sinopse escrita por você."
)

if not CAMINHO_DADOS.exists():
    st.error(
        "O arquivo dados.csv não foi encontrado. "
        "Coloque-o na mesma pasta do arquivo app.py."
    )
    st.stop()

try:
    livros = carregar_livros(str(CAMINHO_DADOS))
    vetorizador, matriz_tfidf = treinar_modelo(
        tuple(livros["descricao"].tolist())
    )
except Exception as erro:
    st.error(f"Erro ao carregar os dados ou preparar o modelo: {erro}")
    st.stop()

st.caption(f"Catálogo disponível: {len(livros):,} livros com sinopse.".replace(",", "."))


# ---------------------------------------------------------
# INTERFACE DE PESQUISA
# ---------------------------------------------------------
aba_livro, aba_sinopse = st.tabs(
    ["🔎 Pesquisar por livro", "✍️ Pesquisar por sinopse"]
)

if "resultados" not in st.session_state:
    st.session_state.resultados = None
if "metadados_pesquisa" not in st.session_state:
    st.session_state.metadados_pesquisa = None
if "avaliacoes" not in st.session_state:
    st.session_state.avaliacoes = {}

with aba_livro:
    st.subheader("Encontre livros parecidos com outro livro")
    st.write("Digite o título no campo abaixo e escolha uma das sugestões.")

    # O próprio selectbox oferece busca digitável dentro do campo de seleção.
    # Assim, não precisamos exibir uma segunda lista de resultados abaixo.
    escolha = st.selectbox(
        "Buscar livro no catálogo:",
        options=livros.index.tolist(),
        index=None,
        placeholder="Comece a digitar o título do livro...",
        format_func=lambda i: f"{livros.loc[i, 'titulo']} — {livros.loc[i, 'autor']}",
        key="livro_selecionado"
    )

    if st.button(
        "Confirmar livro e buscar recomendações",
        key="botao_livro",
        type="primary",
        disabled=escolha is None
    ):
        livro_base = livros.loc[escolha]
        resultados = recomendar_por_livro(
            escolha, matriz_tfidf, livros, QUANTIDADE_RECOMENDACOES
        )
        st.session_state.resultados = resultados
        st.session_state.metadados_pesquisa = {
            "tipo": "Livro",
            "consulta": livro_base["titulo"],
            "titulo_base": livro_base["titulo"],
            "autor_base": livro_base["autor"],
            "descricao_base": livro_base["descricao"]
        }
        st.session_state.avaliacoes = {}

with aba_sinopse:
    st.subheader("Encontre livros a partir de uma descrição")
    texto_livre = st.text_area(
        "Descreva a história, os temas ou o tipo de livro que procura:",
        height=170,
        placeholder=(
            "Ex.: Gostaria de ler uma fantasia sobre uma jovem que descobre "
            "ter poderes mágicos e precisa enfrentar um reino..."
        ),
        key="texto_livre"
    )

    if st.button("Buscar recomendações pela sinopse", key="botao_sinopse", type="primary"):
        if len(texto_livre.strip()) < 20:
            st.warning("Escreva uma descrição um pouco mais detalhada (pelo menos 20 caracteres).")
        else:
            resultados = recomendar_por_texto(
                texto_livre, vetorizador, matriz_tfidf,
                livros, QUANTIDADE_RECOMENDACOES
            )
            if resultados.empty:
                st.warning(
                    "Não encontramos termos reconhecidos pelo modelo nessa descrição. "
                    "Tente usar outras palavras ou temas."
                )
            else:
                st.session_state.resultados = resultados
                st.session_state.metadados_pesquisa = {
                    "tipo": "Sinopse livre",
                    "consulta": texto_livre.strip(),
                    "titulo_base": ""
                }
                st.session_state.avaliacoes = {}


# ---------------------------------------------------------
# EXIBIÇÃO E AVALIAÇÃO DAS RECOMENDAÇÕES
# ---------------------------------------------------------
if st.session_state.resultados is not None:
    resultados = st.session_state.resultados
    metadados = st.session_state.metadados_pesquisa

    st.divider()
    st.header("Suas 5 recomendações")

    if metadados["tipo"] == "Livro":
        st.subheader("Livro escolhido")
        st.markdown(f"**{metadados['titulo_base']}** — {metadados.get('autor_base', 'Autor não informado')}")
        sinopse_base = str(metadados.get("descricao_base", "")).strip()
        if sinopse_base and sinopse_base.lower() != "nan":
            st.markdown("**Sinopse**")
            st.write(sinopse_base)
        else:
            st.caption("Este livro não possui sinopse cadastrada.")
    else:
        st.write("Pesquisa realizada a partir da sinopse informada.")

    st.write(
        "Se desejar, avalie cada indicação. Você pode deixar recomendações "
        "sem avaliação."
    )

    for numero, (_, livro) in enumerate(resultados.iterrows(), start=1):
        titulo = str(livro["titulo"])
        autor = str(livro["autor"])
        descricao = str(livro.get("descricao", "")).strip()
        similaridade = float(livro["similaridade"])

        with st.container(border=True):
            col_info, col_nota = st.columns([4, 1])

            with col_info:
                st.markdown(f"**{numero}. {titulo}**")
                st.write(f"Autor: {autor}")
                st.markdown("**Sinopse**")
                if descricao and descricao.lower() != "nan":
                    st.write(descricao)
                else:
                    st.caption("Sinopse não disponível.")
                st.caption(f"Similaridade textual: {similaridade:.1%}")

            with col_nota:
                chave = f"avaliacao_{numero}"
                st.radio(
                    "Sua avaliação:",
                    options=["Não avaliado", "👍 Gostei", "👎 Não gostei"],
                    key=chave,
                    label_visibility="collapsed"
                )

    st.divider()
    if st.button("Enviar minhas avaliações", type="primary", key="enviar_avaliacoes"):
        registros = []
        data_hora = datetime.now(timezone.utc).isoformat()

        for numero, (_, livro) in enumerate(resultados.iterrows(), start=1):
            avaliacao = st.session_state.get(
                f"avaliacao_{numero}", "Não avaliado"
            )

            if avaliacao == "Não avaliado":
                continue

            registros.append({
                "data_hora_utc": data_hora,
                "tipo_pesquisa": metadados["tipo"],
                "consulta": metadados["consulta"],
                "titulo_base": metadados["titulo_base"],
                "titulo_recomendado": str(livro["titulo"]),
                "autor_recomendado": str(livro["autor"]),
                "genero_recomendado": str(livro.get("genero", "")),
                "similaridade": round(float(livro["similaridade"]), 6),
                "avaliacao": "Gostei" if avaliacao == "👍 Gostei" else "Não gostei"
            })

        if not registros:
            st.warning("Você ainda não selecionou nenhuma avaliação.")
        else:
            sucesso, mensagem = registrar_avaliacoes_google_sheets(registros)
            if sucesso:
                st.success(mensagem)
                for numero in range(1, len(resultados) + 1):
                    st.session_state[f"avaliacao_{numero}"] = "Não avaliado"
            else:
                st.error(mensagem)

st.divider()
st.caption(
    "As recomendações são calculadas por similaridade textual (TF-IDF e "
    "similaridade do cosseno). Uma pontuação maior indica maior semelhança "
    "entre os textos, mas não garante preferência pessoal."
)
