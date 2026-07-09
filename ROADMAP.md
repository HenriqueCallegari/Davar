# Roadmap — Bíblia KJA

Plataforma de leitura e estudo bíblico. Este documento registra o que já está
implementado e como os próximos módulos se encaixam na arquitetura atual.

## Arquitetura

```
web.py                     # entrypoint WSGI (gunicorn web:app)
app/
  __init__.py              # application factory + injeção de dependências (Services)
  config.py                # configuração central (paths, env, regras)
  core/                    # utilidades transversais (markdown seguro, etc.)
  bible/                   # BibleRepository + rotas (catálogo, leitura, busca)
  plans/                   # ReadingPlanRepository + rotas (planos, progresso, stats, conquistas)
  study/                   # StudyRepository + ThemeService + rotas (grifos, notas, coleções, temas)
  gamification/            # quiz + rotas (jogos, conquistas)
  dashboard/               # dashboard + crescimento + PWA (sw/manifest)
  templates/               # base.html + pages/ (todas herdam do layout premium)
  static/                  # css/ js/ icons/ (design system + comportamento por página)
data/                      # biblia.json, themes.json (dados estáticos)
instance/                  # banco SQLite (gerado, fora do git)
```

Princípios aplicados: **factory + blueprints** (separação de responsabilidades),
repositórios como única fonte de acesso a dados (SRP/DIP), `base.html` único (DRY),
tokens de design (KISS), tipagem e docstrings essenciais.

## ✅ Implementado

- **Dashboard espiritual** — continuar de onde parou, sequência, totais, versículo do dia, atalhos.
- **Leitura premium** — grifos por cor (5 cores com significado), favoritos, anotações markdown,
  TTS versículo a versículo com destaque, modo foco, Pomodoro, barra de rolagem, auto-marcar lido,
  navegação entre capítulos (inclusive entre livros), fonte ajustável.
- **Módulo Estudo** — hub com grifos/favoritos/anotações/coleções, busca em anotações, exportação JSON.
- **Índice temático** — 14 temas que reúnem versículos automaticamente (busca por palavra inteira).
- **Busca global** — palavra/frase, tolerante a acento e caixa, filtros por testamento e livro.
- **Planos de leitura** — NT, AT e Porção Diária anual, progresso, notas, estatísticas.
- **Gamificação** — sequência de calendário, 10 conquistas, quiz de versículos, ordenar os livros.
- **Painel de crescimento** — heatmap de consistência + gráfico semanal (SVG/CSS, sem libs externas).
- **PWA** — manifest + service worker (app shell). Instalável; base para offline.
- **Acessibilidade/UX** — skip-link, foco visível, `prefers-reduced-motion`, tema claro/escuro, mobile.

## 🔜 Próximos módulos (dependem de dataset/serviço)

Cada um encaixa em um blueprint novo (`app/<modulo>/`) com seu repositório/serviço.
Foram deixados de fora por exigirem **dados curados** que não devem ser inventados
(precisão bíblica) ou **chave de API**.

| Módulo | O que falta | Onde entra |
|--------|-------------|------------|
| Referências cruzadas / profecias | Dataset de cross-references (ex.: TSK aberto) em `data/cross_refs.json` | `bible/` — anexar às marcas do versículo na leitura |
| Pessoas (biografia, genealogia, relações) | Dataset curado em `data/pessoas.json` | novo blueprint `people/` + páginas |
| Lugares / Mapas | Coordenadas + eventos em `data/lugares.json` + camada de mapa offline | novo blueprint `places/` |
| Linha do tempo | Cronologia curada em `data/timeline.json` | novo blueprint `timeline/` |
| Companheiro com IA | Chave da Claude API (`ANTHROPIC_API_KEY`) | `study/` — rota `/api/estudo/ia` enviando o capítulo como contexto |
| Devocionais | `data/devocionais.json` (config já prevê `DEVOTIONALS_PATH`) | `study/` |
| Planos personalizados | Formulário + geração de schedule sob demanda | `plans/` (schedule já é data-driven) |
| Sincronização em nuvem / login / multi-dispositivo | Auth + `user_id` nas tabelas (já isoladas por repositório) | `core/auth/` + coluna `user_id` |
| Offline completo | Precache de páginas/capítulos no service worker | `static/sw.js` |
