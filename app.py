"""
CopaGPT — Agente Text-to-SQL Standalone
=======================================

Fluxo:

Usuário
   ↓
LLM gera SQL
   ↓
Guardrails
   ↓
SQLite
   ↓
Resultado
   ↓
LLM explica
   ↓
Usuário

Se o SQL falhar:
Erro → LLM → novo SQL → SQLite
"""

import os
import re
import sqlite3
from dataclasses import dataclass

import pandas as pd
import streamlit as st
from groq import Groq


# ============================================================
# CONFIGURAÇÃO
# ============================================================

DB_PATH = "copa.db"

GROQ_MODEL = "llama-3.3-70b-versatile"

MAX_TENTATIVAS = 3

GROQ_API_KEY = os.getenv("GROQ_API_KEY")


if not GROQ_API_KEY:
    st.error(
        "A variável de ambiente GROQ_API_KEY não foi configurada."
    )
    st.stop()


cliente = Groq(
    api_key=GROQ_API_KEY
)


# ============================================================
# RESULTADO DO AGENTE
# ============================================================

@dataclass
class Resultado:

    resposta: str

    sql: str | None = None

    df: pd.DataFrame | None = None

    erro: str | None = None

    tentativas: int = 0


# ============================================================
# BANCO DE DADOS
# ============================================================

def conectar():

    # Abre explicitamente em modo somente leitura.

    uri = f"file:{os.path.abspath(DB_PATH)}?mode=ro"

    return sqlite3.connect(
        uri,
        uri=True
    )


def montar_schema():

    """
    Descobre automaticamente quais tabelas e colunas
    existem no SQLite.

    Esse schema será enviado para a LLM.
    """

    conn = conectar()

    cursor = conn.cursor()

    tabelas = cursor.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type='table'
        AND name NOT LIKE 'sqlite_%'
        """
    ).fetchall()


    partes = []


    for (tabela,) in tabelas:

        colunas = cursor.execute(
            f'PRAGMA table_info("{tabela}")'
        ).fetchall()


        descricao = [
            f"TABELA: {tabela}"
        ]


        for coluna in colunas:

            nome = coluna[1]
            tipo = coluna[2]

            descricao.append(
                f"- {nome} ({tipo})"
            )


        partes.append(
            "\n".join(descricao)
        )


    conn.close()


    return "\n\n".join(partes)


# ============================================================
# PROMPT
# ============================================================

def montar_prompt_sql(
    pergunta,
    erro_anterior=None,
    sql_anterior=None
):

    schema = montar_schema()


    prompt = f"""
Você é um agente especialista em análise de dados usando SQLite.

Sua tarefa é transformar a pergunta do usuário em UMA consulta SQL.

BANCO DISPONÍVEL:

{schema}


REGRAS OBRIGATÓRIAS:

1. Gere somente SELECT.
2. Nunca use INSERT.
3. Nunca use UPDATE.
4. Nunca use DELETE.
5. Nunca use DROP.
6. Nunca use ALTER.
7. Nunca modifique o banco.
8. Use somente tabelas e colunas existentes no schema.
9. Prefira consultas simples.
10. Limite resultados grandes usando LIMIT.
11. Responda SOMENTE com o SQL.
12. Não use ```sql.
13. Não explique o SQL.


PERGUNTA DO USUÁRIO:

{pergunta}
"""


    # Se estamos tentando corrigir uma consulta:

    if erro_anterior:

        prompt += f"""


A consulta anterior foi:

{sql_anterior}


Ela retornou este erro:

{erro_anterior}


Analise o erro e gere uma nova consulta corrigida.
"""


    return prompt


# ============================================================
# CHAMAR LLM
# ============================================================

def chamar_llm(prompt):

    resposta = cliente.chat.completions.create(

        model=GROQ_MODEL,

        messages=[

            {
                "role": "system",
                "content": (
                    "Você é especialista em SQLite "
                    "e análise de dados."
                )
            },

            {
                "role": "user",
                "content": prompt
            }
        ],

        temperature=0
    )


    return resposta.choices[0].message.content.strip()


# ============================================================
# LIMPAR SQL
# ============================================================

def limpar_sql(sql):

    sql = sql.strip()


    sql = re.sub(
        r"^```sql",
        "",
        sql,
        flags=re.IGNORECASE
    )


    sql = re.sub(
        r"^```",
        "",
        sql
    )


    sql = re.sub(
        r"```$",
        "",
        sql
    )


    return sql.strip()


# ============================================================
# GUARDRAILS
# ============================================================

def validar_sql(sql):

    """
    Não confiamos apenas no prompt.

    A aplicação também verifica o SQL antes
    de permitir que ele chegue ao banco.
    """

    sql_limpo = sql.strip()

    sql_upper = sql_limpo.upper()


    # --------------------------------------------------------
    # Deve começar com SELECT ou WITH
    # --------------------------------------------------------

    if not (
        sql_upper.startswith("SELECT")
        or sql_upper.startswith("WITH")
    ):

        return False, "Somente consultas SELECT são permitidas."


    # --------------------------------------------------------
    # Palavras proibidas
    # --------------------------------------------------------

    proibidos = [

        "INSERT",
        "UPDATE",
        "DELETE",
        "DROP",
        "ALTER",
        "CREATE",
        "REPLACE",
        "TRUNCATE",
        "ATTACH",
        "DETACH",
        "PRAGMA"
    ]


    for palavra in proibidos:

        if re.search(
            rf"\b{palavra}\b",
            sql_upper
        ):

            return (
                False,
                f"Comando proibido detectado: {palavra}"
            )


    # --------------------------------------------------------
    # Não permitir múltiplos comandos
    # --------------------------------------------------------

    sem_final = sql_limpo.rstrip(";")

    if ";" in sem_final:

        return (
            False,
            "Múltiplos comandos SQL não são permitidos."
        )


    return True, None


# ============================================================
# EXECUTAR SQL
# ============================================================

def executar_sql(sql):

    valido, erro = validar_sql(sql)


    if not valido:

        raise ValueError(erro)


    conn = conectar()


    try:

        df = pd.read_sql_query(
            sql,
            conn
        )

    finally:

        conn.close()


    return df


# ============================================================
# TRANSFORMAR RESULTADO EM TEXTO
# ============================================================

def dataframe_para_contexto(df):

    if df.empty:

        return "A consulta não retornou resultados."


    # Evita mandar uma quantidade absurda de dados para a LLM.

    limitado = df.head(50)


    return limitado.to_csv(
        index=False
    )


# ============================================================
# LLM EXPLICA RESULTADO
# ============================================================

def explicar_resultado(
    pergunta,
    sql,
    df
):

    dados = dataframe_para_contexto(df)


    prompt = f"""
Você é um assistente de análise de dados.

O usuário perguntou:

{pergunta}


A consulta executada foi:

{sql}


O banco retornou:

{dados}


Responda à pergunta usando SOMENTE os dados retornados.

Seja direto e claro.

Não invente informações.

Não explique SQL a menos que seja necessário.
"""


    return chamar_llm(prompt)


# ============================================================
# 🧠 AGENTE
# ============================================================

def perguntar(pergunta):

    """
    Este é o coração do agente.

    PERGUNTA
        ↓
    LLM
        ↓
    SQL
        ↓
    GUARDRAILS
        ↓
    SQLITE
        ↓
    OBSERVAÇÃO

    Se houver erro:

        ERRO
         ↓
        LLM
         ↓
      NOVO SQL
         ↓
        RETRY
    """


    erro_anterior = None

    sql_anterior = None


    for tentativa in range(
        1,
        MAX_TENTATIVAS + 1
    ):


        # ----------------------------------------------------
        # THINK / DECIDE
        # ----------------------------------------------------

        prompt = montar_prompt_sql(

            pergunta,

            erro_anterior,

            sql_anterior
        )


        sql = chamar_llm(prompt)

        sql = limpar_sql(sql)


        # ----------------------------------------------------
        # ACTION
        # ----------------------------------------------------

        try:

            df = executar_sql(sql)


            # ------------------------------------------------
            # RESULTADO
            # ------------------------------------------------

            resposta = explicar_resultado(

                pergunta,

                sql,

                df
            )


            return Resultado(

                resposta=resposta,

                sql=sql,

                df=df,

                tentativas=tentativa
            )


        # ----------------------------------------------------
        # OBSERVATION
        # ----------------------------------------------------

        except Exception as e:

            erro_anterior = str(e)

            sql_anterior = sql


    # ========================================================
    # TODAS AS TENTATIVAS FALHARAM
    # ========================================================

    return Resultado(

        resposta=(
            "Não consegui responder essa pergunta "
            "usando o banco de dados."
        ),

        sql=sql_anterior,

        erro=erro_anterior,

        tentativas=MAX_TENTATIVAS
    )


# ============================================================
# INTERFACE
# ============================================================

st.set_page_config(

    page_title="CopaGPT",

    page_icon="⚽",

    layout="wide"
)


st.title("⚽ CopaGPT")


st.caption(
    "Faça perguntas em português sobre os dados das Copas do Mundo."
)


# ============================================================
# SESSION STATE
# ============================================================

if "mensagens" not in st.session_state:

    st.session_state.mensagens = []


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.header("⚙️ Configurações")


    st.success(
        f"LLM conectado\n\n`{GROQ_MODEL}`"
    )


    mostrar_sql = st.checkbox(

        "Mostrar SQL gerado",

        value=True
    )


    # --------------------------------------------------------
    # SCHEMA
    # --------------------------------------------------------

    with st.expander(
        "🗄️ Estrutura do banco"
    ):

        try:

            st.code(
                montar_schema(),
                language="text"
            )

        except Exception as e:

            st.error(str(e))


    st.divider()


    # --------------------------------------------------------
    # LIMPAR
    # --------------------------------------------------------

    if st.button(
        "🗑️ Limpar conversa",
        use_container_width=True
    ):

        st.session_state.mensagens = []

        st.rerun()


# ============================================================
# DESENHAR RESPOSTA
# ============================================================

def desenhar_resposta(msg):

    if msg.get("erro"):

        st.error(
            msg["erro"]
        )

        return


    st.markdown(
        msg["conteudo"]
    )


    # --------------------------------------------------------
    # SQL
    # --------------------------------------------------------

    if (
        mostrar_sql
        and msg.get("sql")
    ):

        with st.expander(
            f"🔍 SQL gerado — "
            f"{msg['tentativas']} tentativa(s)"
        ):

            st.code(
                msg["sql"],
                language="sql"
            )


    # --------------------------------------------------------
    # DATAFRAME
    # --------------------------------------------------------

    df = msg.get("df")


    if df is not None:

        st.dataframe(

            df,

            use_container_width=True,

            hide_index=True
        )


        # ----------------------------------------------------
        # GRÁFICO AUTOMÁTICO
        # ----------------------------------------------------

        if (

            df.shape[1] == 2

            and 2 <= len(df) <= 30

            and pd.api.types.is_numeric_dtype(
                df.iloc[:, 1]
            )

        ):

            st.bar_chart(

                df,

                x=df.columns[0],

                y=df.columns[1]
            )


# ============================================================
# HISTÓRICO
# ============================================================

for msg in st.session_state.mensagens:

    with st.chat_message(
        msg["role"]
    ):

        if msg["role"] == "user":

            st.markdown(
                msg["conteudo"]
            )

        else:

            desenhar_resposta(msg)


# ============================================================
# CHAT
# ============================================================

pergunta = st.chat_input(
    "Ex.: Quem foi o jogador com mais gols?"
)


if pergunta:


    # --------------------------------------------------------
    # USUÁRIO
    # --------------------------------------------------------

    st.session_state.mensagens.append({

        "role": "user",

        "conteudo": pergunta
    })


    with st.chat_message("user"):

        st.markdown(
            pergunta
        )


    # --------------------------------------------------------
    # AGENTE
    # --------------------------------------------------------

    with st.chat_message("assistant"):


        with st.spinner(
            "🧠 Analisando os dados..."
        ):

            resultado = perguntar(
                pergunta
            )


        msg = {

            "role": "assistant",

            "conteudo": resultado.resposta,

            "sql": resultado.sql,

            "df": resultado.df,

            "erro": resultado.erro,

            "tentativas": resultado.tentativas
        }


        st.session_state.mensagens.append(
            msg
        )


        desenhar_resposta(msg)