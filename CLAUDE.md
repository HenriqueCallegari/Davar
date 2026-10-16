# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## O que é

DAVAR (bibliakja) é uma plataforma de leitura e estudo bíblico em Flask, sem
cadastro obrigatório de terceiros e sem fins lucrativos. Backend em Python
puro (sem ORM), frontend em HTML/CSS/JS sem framework nem build step —
arquivos servidos diretamente pela pasta `app/static/`.

## Comandos

```bash
# Setup
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt

# Rodar em desenvolvimento (Flask debug via __main__ de web.py)
python web.py                  # http://127.0.0.1:5000

# Rodar como em produção (gunicorn, usado no Procfile/Render)
gunicorn web:app --bind 0.0.0.0:5000
```

Testes (stdlib `unittest`, sem pytest): `python -m unittest discover -s tests -t .`
— cobrem backup/restauração, planos, segurança (CSRF, login, SECRET_KEY) e
validação das APIs. Não há linter nem type checker configurados; não assuma
`pytest`, `ruff` ou `flake8` disponíveis.

## Arquitetura

**Application factory + blueprints por domínio.** `web.py` expõe `app =
create_app()` (WSGI); `app/__init__.py` monta a app, instancia todos os
repositórios uma única vez em `Services` (dataclass acessível via
`current_app.services`) e registra os blueprints. Não há DI framework —
é injeção manual simples via esse container.

Blueprints (cada um em `app/<dominio>/`, com `routes.py` + repositório/serviço
próprio):
- `auth/` — contas (`AuthRepository`), login/registro/logout.
- `bible/` — catálogo, leitura de capítulos, busca global (`BibleRepository`,
  `BibleLibrary`).
- `plans/` — planos de leitura, progresso, estatísticas, conquistas
  (`ReadingPlanRepository`).
- `study/` — grifos, notas, favoritos, coleções, temas, cartões de memorização
  com repetição espaçada em caixas de Leitner (`StudyRepository`,
  `ThemeService`, `ChapterStudyService`).
- `gamification/` — quiz de versículos, ordenar livros e os jogos gerados do
  texto bíblico (`games.py`: completar, montar, relâmpago, pares; catálogo
  `JOGOS` em `routes.py`, interface em `static/js/jogos.js`). Todos usam a
  versão ativa, aceitam escopo `?livro=&capitulo=` e o desafio do dia
  (`?diario=1`, semente = data). Nunca invente conteúdo bíblico: gere só do texto.
- `dashboard/` — home, painel de crescimento, service worker/manifest (PWA).
- `core/` — utilidades transversais: sessão/auth (`core/auth.py`), versão
  bíblica ativa por cookie (`core/version.py`), markdown seguro
  (`core/text.py`), cliente Turso (`core/turso.py`), gerência de dados por
  usuário (`core/user_data.py`).

**Repositórios são a única porta de acesso a dados** — nunca acesse SQLite ou
os JSONs da Bíblia diretamente de uma rota; sempre through o repositório do
domínio.

### Multi-versão bíblica

`BibleLibrary` (`app/bible/library.py`) carrega todas as versões configuradas
em `Config.BIBLE_VERSIONS` (hoje KJA e NTLH). A versão **default** define o
cânon (ordem de livros, abreviações, nº de capítulos); as demais são
normalizadas por **posição** contra esse cânon em `_normalize`, aparando
capítulos excedentes. Isso mantém grifos/progresso/URLs estáveis
independente da versão ativa, porque tudo é referenciado por `abbrev` do
cânon, não pelo texto de uma tradução específica. A versão ativa por request
vem de `core/version.py`, resolvida por cookie (`Config.VERSION_COOKIE`).

### Persistência: um SQLite por usuário + backup opcional no Turso

Não há ORM. Cada usuário tem seu próprio arquivo SQLite
(`instance/users/user_<id>.sqlite3`, WAL + busy_timeout via `core/db.py`), aberto sob demanda e cacheado em
memória por `UserDataManager` (`app/core/user_data.py`), que expõe
`ReadingPlanRepository` e `StudyRepository` por usuário. Contas
(`AuthRepository`) e progresso/estudo usam bancos separados.

Se `TURSO_DATABASE_URL`/`TURSO_AUTH_TOKEN` estiverem configurados
(`Config.turso_enabled()`), o disco efêmero de planos free deixa de ser um
problema: ao abrir um usuário cujo banco local não existe, `UserDataManager`
restaura do Turso; após cada escrita (`after_request` em `app/__init__.py`),
agenda um backup assíncrono (compacta o `.sqlite3` inteiro em gzip e sobe como
blob). Sem Turso configurado, tudo roda 100% local. O backup usa a API de backup do SQLite (snapshot consistente) com debounce
(`BACKUP_DEBOUNCE_SECONDS`, padrão 5s) e é enviado também no `atexit`. Se o banco
local não existe e a restauração falha, `UserDataManager.get` levanta
`UserDataUnavailable` (503) em vez de criar um banco vazio — isso evita que o
próximo backup sobrescreva o backup bom na nuvem. `TursoClient`
(`app/core/turso.py`) é um cliente HTTP mínimo (Hrana v2 pipeline) escrito com
`urllib` puro — sem dependência nativa de libSQL.

### Autenticação

Sessão simples via Flask `session` (`app/core/auth.py`), sem tokens JWT.
Todo POST/PUT/PATCH/DELETE exige token CSRF (`core/security.py`): campo
`csrf_token` nos formulários, cabeçalho `X-CSRF-Token` no `fetch` (o `app.js`
lê a `<meta name="csrf-token">`; use `window.postJSON`/`apiJSON`). `/api/*` sem
sessão responde 401 JSON. Login tem limite de tentativas (por e-mail e IP).
`SECRET_KEY` é obrigatória em produção (detectada por `RENDER` ou
`APP_ENV=production`; `Config.resolve_secret_key`) — o app não sobe sem ela.
Em desenvolvimento, sem a variável, usa uma chave aleatória por processo.
`PUBLIC_ENDPOINTS` em `app/__init__.py` lista os únicos endpoints acessíveis
sem login; o `before_request` global redireciona todo o resto para
`auth.login` se não houver `user_id` na sessão. Ao adicionar uma rota
pública nova (ex.: outro endpoint de PWA), é preciso adicioná-la a esse set.

### Dados estáticos vs. gerados pelo usuário

- `data/biblia.json`, `data/ntlh.json` — texto bíblico (grande, ~4-5MB cada).
- `data/themes.json` — índice temático (slug + palavras-chave por tema);
  `ThemeService` casa por **palavra inteira** normalizada (sem acento/caixa)
  contra o índice plano da Bíblia, com cache em memória por tema.
- `data/estudos/<abbrev>.json` — síntese teológica **escrita à mão** por
  capítulo (não gerada por IA em tempo real); `ChapterStudyService` apenas lê
  esses arquivos. O contrato de `generate()` mantém a assinatura antiga
  (baseada em IA) por compatibilidade com a rota, mas ignora
  `version_id`/`verses`: o conteúdo é o mesmo independente da tradução.

### Convenções de nomenclatura

O domínio é em português: nomes de rota, campos de banco, chaves de JSON e
templates usam português (`livro`, `capitulo`, `versiculo`, `plano_id`,
`nome`, `criado_em`). Não traduza para inglês ao adicionar campos novos —
mantenha consistência com o que já existe em cada tabela/repositório. Nomes
de classes, módulos e comentários de código, por outro lado, seguem em
português também (docstrings do projeto estão todas em PT-BR).

Rotas de página usam URLs "bonitas" em português (`/livro/<abbrev>/capitulo/<num>`,
`/planos/<id>`); endpoints de API JSON ficam sob `/api/<dominio>/...` e usam
métodos HTTP explícitos (`@bp.post`, `@bp.delete`) em vez de `methods=[...]`.

### Frontend

Sem bundler, sem framework JS. `app/static/css/app.css` é um design system
próprio baseado em tokens (CSS variables) com tema claro/escuro. Cada página
com comportamento interativo tem seu próprio arquivo em `app/static/js/`
(`reading.js`, `plano.js`, `quiz.js`, `ordenar.js`, `player.js`), carregado
só na página correspondente — não há um bundle único. `app/templates/base.html`
é o único layout premium; todas as páginas em `templates/pages/` estendem
dele (evita duplicação de head/nav/footer).

PWA: `app/static/sw.js` e `app/static/manifest.webmanifest` são servidos na
**raiz** do site (não em `/static/...`) via rotas dedicadas em
`dashboard/routes.py`, porque um service worker só tem escopo sobre o que
está "abaixo" do seu próprio caminho.

## Próximos módulos planejados

Ver `ROADMAP.md` para a lista de módulos futuros (referências cruzadas,
pessoas, lugares/mapas, linha do tempo, companheiro com IA, devocionais,
planos personalizados, sync em nuvem/login, offline completo) e onde cada um
se encaixaria na arquitetura de blueprints atual.
