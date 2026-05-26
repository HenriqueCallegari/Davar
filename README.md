<div align="center">

<img src="https://capsule-render.vercel.app/api?type=waving&color=0:1e3a8a,100:6d28d9&height=200&section=header&text=Biblia%20KJA&fontSize=64&fontColor=ffffff&animation=fadeIn&fontAlignY=38&desc=Leitura%20da%20Biblia%20no%20navegador&descAlignY=60&descSize=18" alt="header" />

<br />

<a href="https://github.com/HenriqueCallegari/bibliakja/stargazers">
  <img src="https://custom-icon-badges.demolab.com/github/stars/HenriqueCallegari/bibliakja?style=for-the-badge&logo=star&color=f1c40f&logoColor=white&labelColor=2c2f33" alt="Stars" />
</a>
<a href="LICENSE">
  <img src="https://custom-icon-badges.demolab.com/badge/license-MIT-3b82f6?style=for-the-badge&logo=law&logoColor=white&labelColor=2c2f33" alt="License" />
</a>
<a href="https://github.com/HenriqueCallegari/bibliakja/commits/main">
  <img src="https://custom-icon-badges.demolab.com/github/last-commit/HenriqueCallegari/bibliakja?style=for-the-badge&logo=history&color=ef4444&logoColor=white&labelColor=2c2f33" alt="Last commit" />
</a>

</div>

---

## Sobre o projeto

Um site simples pra ler a **Bíblia (versão King James Atualizada)** direto no navegador, sem precisar baixar app nem fazer cadastro.

A ideia veio do uso pessoal pra **devocionais diárias** — abre a página, escolhe o livro, escolhe o capítulo, lê. Só isso.

### Como funciona pra quem usa

1. Abre o site → vê a lista dos 66 livros da Bíblia
2. Clica num livro → aparecem os capítulos disponíveis
3. Clica num capítulo → lê os versículos um após o outro
4. Funciona no celular, tablet e computador

<br />

## Stack

<div align="center">

<a href="https://skillicons.dev">
  <img src="https://skillicons.dev/icons?i=python,flask,html,css&theme=dark" alt="stack" />
</a>

</div>

| O que | Por que |
|---|---|
| **Python** | Linguagem que roda por trás do site |
| **Flask** | Framework leve pra montar páginas web em Python — perfeito pra projeto pequeno |
| **HTML / CSS** | Estrutura e visual das páginas |
| **JSON** | Os textos da Bíblia ficam num único arquivo organizado por livro/capítulo/versículo (parecido com uma planilha hierárquica) |

<br />

## Como rodar no seu computador

```bash
# 1. Baixa o projeto
git clone https://github.com/HenriqueCallegari/bibliakja.git
cd bibliakja

# 2. Cria um ambiente isolado (recomendado, evita conflito de pacotes)
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# 3. Instala as dependências
pip install -r requirements.txt

# 4. Sobe o site
python web.py
```

Abre o navegador em **http://127.0.0.1:5000** e pronto.

<br />

## Estrutura

```
bibliakja/
├── web.py              # O servidor web — responde quando alguém abre uma página
├── main.py             # Versão de terminal (linha de comando), pra consulta rápida
├── biblia.json         # Texto completo da Bíblia organizado
├── requirements.txt    # Lista de pacotes Python que o projeto precisa
├── templates/          # As páginas HTML que o usuário vê
│   ├── livros.html         → lista de livros
│   ├── capitulos.html      → lista de capítulos de um livro
│   └── capitulo.html       → texto de um capítulo
└── static/
    └── style.css       # Visual: cores, fontes, espaçamento
```

<br />

## Versão extra: terminal

Tem também o `main.py` — uma versão que roda direto no terminal pra quem prefere consultar versículos rápido sem abrir navegador:

```bash
python main.py
```

Aí é só digitar a abreviação do livro (ex: `gn` pra Gênesis), o capítulo e o versículo.

<br />

## Autor

<div align="center">

**Henrique Callegari**

<a href="https://github.com/HenriqueCallegari">
  <img src="https://custom-icon-badges.demolab.com/badge/-GitHub-181717?style=for-the-badge&logo=github&logoColor=white" alt="GitHub" />
</a>
<a href="https://www.linkedin.com/in/henrique-callegari-/">
  <img src="https://custom-icon-badges.demolab.com/badge/-LinkedIn-0A66C2?style=for-the-badge&logo=linkedin&logoColor=white" alt="LinkedIn" />
</a>

</div>

<br />

<div align="center">

<img src="https://capsule-render.vercel.app/api?type=waving&color=0:6d28d9,100:1e3a8a&height=100&section=footer" alt="footer" />

</div>
