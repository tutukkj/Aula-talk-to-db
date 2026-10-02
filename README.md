# CopaGPT

Agente de IA que responde perguntas em português sobre estatísticas de jogadores das Copas do Mundo. A aplicação transforma a pergunta em SQL, valida a consulta, executa somente leitura no SQLite e explica o resultado usando um modelo da Groq.

## Acesso rápido

- [Abrir o Google Colab](https://colab.research.google.com/): use o notebook `copagpt.ipynb` desta pasta em **File > Upload notebook**.
- **Aplicação em produção:** configure aqui a URL publicada do Streamlit: `https://aula-talk-to-db-eoam645gjfytummvom5tjs.streamlit.app/`.


## O que a aula demonstra

O projeto apresenta, na prática, como construir um agente Text-to-SQL:

```text
Pergunta em português
        ↓
LLM gera SQL
        ↓
Guardrails validam a consulta
        ↓
SQLite executa em modo somente leitura
        ↓
LLM explica o resultado
```

Durante a aula, os principais conceitos são:

- LLM, tokens e janela de contexto;
- diferença entre um chat e um agente;
- schema como contexto para geração de SQL;
- validação de comandos e proteção contra alterações no banco;
- loop de tentativa e correção quando o SQL falha;
- uso de Streamlit para transformar o agente em uma aplicação web.

## Arquivos

| Arquivo | Descrição |
|---|---|
| `copagpt.ipynb` | Notebook da aula, preparado para execução no Google Colab. |
| `app.py` | Aplicação web em Streamlit. |
| `copa.db` | Banco SQLite consultado pelo agente. |
| `requirements.txt` | Dependências Python. |

## Usar no Google Colab

1. Abra o [Google Colab](https://colab.research.google.com/).
2. Faça upload de `copagpt.ipynb`.
3. Execute as células na ordem.
4. Quando solicitado, envie o arquivo `copa.db` criado no Dia 1.
5. Para usar a Groq, abra **Secrets** no menu lateral e crie o segredo `GROQ_API_KEY`, habilitando **Notebook access**.
6. Sem chave ou sem internet, o notebook pode funcionar no modo offline com as perguntas de exemplo.

A chave nunca deve ser escrita diretamente no notebook ou commitada no repositório.

## Executar localmente

Requisitos: Python 3.10 ou superior.

```bash
cd agente_standalone
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export GROQ_API_KEY="sua-chave-da-groq"
streamlit run app.py
```

No Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:GROQ_API_KEY = "sua-chave-da-groq"
python -m streamlit run app.py
```

A aplicação será aberta em `http://localhost:8501`.

A chave pode ser criada no [console da Groq](https://console.groq.com/keys). O modelo usado pelo app está definido em `GROQ_MODEL` no código.

## Como usar a aplicação

Digite perguntas como:

- `Quem foi o artilheiro de 2022?`
- `Quais jogadores fizeram mais gols pelo Brazil?`
- `Qual seleção teve mais jogadores convocados em 2018?`

A barra lateral permite mostrar o SQL gerado, consultar o schema do banco e limpar a conversa. O banco é aberto em modo somente leitura e o agente permite apenas consultas `SELECT` ou `WITH`.

## Publicar em produção

A forma mais simples é publicar o repositório no Streamlit Community Cloud:

1. Suba a pasta em um repositório GitHub.
2. Crie uma aplicação em [share.streamlit.io](https://share.streamlit.io/).
3. Selecione `agente_standalone/app.py` como arquivo principal.
4. Garanta que `copa.db` esteja no mesmo diretório do `app.py`.
5. Em **Settings > Secrets**, adicione:

```toml
GROQ_API_KEY = "sua-chave-da-groq"
```

6. Copie a URL gerada pelo Streamlit e substitua o campo **Aplicação em produção** no início deste README.

Nunca coloque a chave da Groq no código, no notebook ou em um arquivo versionado.

## Observações

- O arquivo `copa.db` precisa existir no diretório atual da aplicação.
- O modo online exige uma chave válida da Groq e acesso à internet.
- O modo offline do notebook é adequado para a demonstração da validação e execução SQL, mas responde apenas às perguntas de exemplo.
