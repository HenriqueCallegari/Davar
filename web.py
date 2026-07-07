import json
import os
import random

from flask import Flask, jsonify, render_template, request

from reading_repository import ReadingPlanRepository


app = Flask(__name__)

with open("biblia.json", "r", encoding="utf-8-sig") as f:
    biblia = json.load(f)

reading_repository = ReadingPlanRepository(biblia)

BOOK_NAMES = [livro["name"] for livro in biblia]


def _build_quiz_questions(quantidade: int = 10) -> list[dict]:
    """Gera perguntas 'de qual livro e este versiculo?' a partir da biblia."""
    perguntas: list[dict] = []
    tentativas = 0
    while len(perguntas) < quantidade and tentativas < quantidade * 40:
        tentativas += 1
        livro = random.choice(biblia)
        if not livro["chapters"]:
            continue
        cap_index = random.randrange(len(livro["chapters"]))
        capitulo = livro["chapters"][cap_index]
        if not capitulo:
            continue
        verso_index = random.randrange(len(capitulo))
        texto = str(capitulo[verso_index]).strip()
        if not (55 <= len(texto) <= 240):
            continue

        distratores = [nome for nome in BOOK_NAMES if nome != livro["name"]]
        opcoes = random.sample(distratores, 3) + [livro["name"]]
        random.shuffle(opcoes)
        perguntas.append(
            {
                "texto": texto,
                "correta": livro["name"],
                "referencia": f"{livro['name']} {cap_index + 1}:{verso_index + 1}",
                "opcoes": opcoes,
            }
        )
    return perguntas


@app.route("/")
def listar_livros():
    livros = [{"abbrev": livro["abbrev"], "name": livro["name"]} for livro in biblia]
    return render_template("livros.html", livros=livros)


@app.route("/planos")
def listar_planos():
    planos = reading_repository.list_plans()
    return render_template("planos.html", planos=planos)


@app.route("/planos/<int:plano_id>")
def mostrar_plano(plano_id):
    dia = request.args.get("dia", type=int)
    dados = reading_repository.get_plan_day(plano_id, dia)
    if dados is None:
        return "Plano nao encontrado.", 404
    return render_template("plano.html", **dados)


@app.route("/planos/<int:plano_id>/estatisticas")
def mostrar_estatisticas(plano_id):
    dados = reading_repository.get_statistics_page(plano_id)
    if dados is None:
        return "Plano nao encontrado.", 404
    return render_template("estatisticas.html", **dados)


@app.post("/api/planos/<int:plano_id>/progresso")
def salvar_progresso(plano_id):
    payload = request.get_json(silent=True) or {}
    livro = str(payload.get("livro", "")).strip()
    capitulo = payload.get("capitulo")
    concluido = bool(payload.get("concluido"))

    if not livro or not isinstance(capitulo, int):
        return jsonify({"erro": "Dados invalidos para atualizar o progresso."}), 400

    resultado = reading_repository.update_progress(plano_id, livro, capitulo, concluido)
    if resultado is None:
        return jsonify({"erro": "Capitulo do plano nao encontrado."}), 404
    return jsonify(resultado)


@app.post("/api/planos/<int:plano_id>/dia/<int:dia>/nota")
def salvar_nota(plano_id, dia):
    payload = request.get_json(silent=True) or {}
    texto = str(payload.get("texto", ""))
    resultado = reading_repository.save_note(plano_id, dia, texto)
    if resultado is None:
        return jsonify({"erro": "Plano nao encontrado."}), 404
    return jsonify(resultado)


@app.route("/conquistas")
def mostrar_conquistas():
    dados = reading_repository.get_achievements()
    return render_template("conquistas.html", **dados)


@app.route("/jogos")
def listar_jogos():
    return render_template("jogos.html")


@app.route("/jogos/quiz")
def jogo_quiz():
    return render_template("quiz.html")


@app.route("/jogos/ordenar")
def jogo_ordenar():
    return render_template("ordenar.html", livros=BOOK_NAMES)


@app.get("/api/quiz")
def api_quiz():
    quantidade = request.args.get("q", default=10, type=int) or 10
    quantidade = max(1, min(quantidade, 20))
    return jsonify({"perguntas": _build_quiz_questions(quantidade)})


@app.route("/livro/<abbrev>")
def mostrar_capitulos(abbrev):
    livro = next((l for l in biblia if l["abbrev"].lower() == abbrev.lower()), None)
    if livro:
        total = len(livro["chapters"])
        return render_template(
            "capitulos.html",
            abbrev=livro["abbrev"],
            name=livro["name"],
            total=total,
        )
    return "Livro nao encontrado.", 404


@app.route("/livro/<abbrev>/capitulo/<int:num>")
def mostrar_capitulo(abbrev, num):
    livro = next((l for l in biblia if l["abbrev"].lower() == abbrev.lower()), None)
    if livro:
        if 1 <= num <= len(livro["chapters"]):
            texto = livro["chapters"][num - 1]
            return render_template(
                "capitulo.html",
                abbrev=livro["abbrev"],
                name=livro["name"],
                num=num,
                texto=texto,
            )
        return "Capitulo nao encontrado.", 404
    return "Livro nao encontrado.", 404


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
