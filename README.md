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

Uma **plataforma de leitura e estudo bíblico** (versão King James Atualizada) que roda no navegador, sem cadastro. Começou como um leitor simples e evoluiu para uma experiência completa: leitura premium, ferramentas de estudo, planos, gamificação e acompanhamento de crescimento.

### O que dá pra fazer

- 📖 **Ler** os 66 livros com tipografia cuidada, tema claro/escuro, modo foco, fonte ajustável e leitura em voz alta (com destaque do versículo).
- 🖊️ **Estudar** — grifar versículos em 5 cores (cada uma com um significado), anotar em markdown com tags, favoritar e organizar em coleções.
- 🔍 **Buscar** qualquer palavra ou frase em toda a Bíblia (ignora acento e maiúsculas).
- 🏷️ **Temas** — 14 temas que reúnem versículos automaticamente (fé, ansiedade, perdão…).
- 🗓️ **Planos de leitura** com progresso, anotações e estatísticas.
- 🔥 **Gamificação** — sequência de dias, 10 conquistas, quiz de versículos e jogo de ordenar os livros.
- 📈 **Crescimento** — dashboard, heatmap de consistência e gráficos de evolução.
- 📲 **PWA** — instalável no celular.

<br />

## Stack

<div align="center">

<a href="https://skillicons.dev">
  <img src="https://skillicons.dev/icons?i=python,flask,sqlite,html,css,js&theme=dark" alt="stack" />
</a>

</div>

| O que | Por que |
|---|---|
| **Python + Flask** | Backend em *application factory* com blueprints por domínio |
| **SQLite** | Progresso, grifos, anotações e coleções persistidos |
| **HTML / CSS / JS** | Design system próprio (tokens, claro/escuro), sem frameworks de front |
| **JSON** | Texto bíblico e índice temático como dados estáticos |
| **PWA** | Manifest + service worker (instalável, base offline) |

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
├── web.py                 # entrypoint WSGI (gunicorn web:app)
├── app/                   # aplicação (factory + blueprints por domínio)
│   ├── __init__.py            → create_app, injeção de dependências
│   ├── config.py              → configuração central
│   ├── core/                  → utilidades (markdown seguro…)
│   ├── bible/                 → catálogo, leitura e busca
│   ├── plans/                 → planos, progresso, conquistas
│   ├── study/                 → grifos, notas, coleções, temas
│   ├── gamification/          → quiz e jogos
│   ├── dashboard/             → dashboard, crescimento, PWA
│   ├── templates/             → base.html + pages/
│   └── static/                → css/ js/ icons/ + manifest/sw
├── data/                  # biblia.json, themes.json
├── instance/              # banco SQLite (gerado)
├── requirements.txt
├── Procfile · runtime.txt
└── ROADMAP.md             # status e próximos módulos
```

A arquitetura segue *application factory* + *blueprints*, com repositórios como
única fonte de acesso a dados. Detalhes e próximos passos em [ROADMAP.md](ROADMAP.md).

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
