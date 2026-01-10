from flask import Flask, render_template, request
import json

app = Flask(__name__)

# Carrega o JSON com a Bíblia (usando utf-8-sig para garantir compatibilidade)
with open('biblia.json', 'r', encoding='utf-8-sig') as f:
    biblia = json.load(f)

# Página inicial — Lista de livros
@app.route('/')
def listar_livros():
    livros = [{'abbrev': livro['abbrev'], 'name': livro['name']} for livro in biblia]
    return render_template('livros.html', livros=livros)

# Página de capítulos de um livro específico
@app.route('/livro/<abbrev>')
def mostrar_capitulos(abbrev):
    livro = next((l for l in biblia if l['abbrev'].lower() == abbrev.lower()), None)
    if livro:
        total = len(livro['chapters'])
        return render_template(
            'capitulos.html',
            abbrev=livro['abbrev'],
            name=livro['name'],
            total=total
        )
    else:
        return "Livro não encontrado.", 404

# Página de versículos de um capítulo específico de um livro
@app.route('/livro/<abbrev>/capitulo/<int:num>')
def mostrar_capitulo(abbrev, num):
    livro = next((l for l in biblia if l['abbrev'].lower() == abbrev.lower()), None)
    if livro:
        if 1 <= num <= len(livro['chapters']):
            texto = livro['chapters'][num-1]
            return render_template(
                'capitulo.html',
                abbrev=livro['abbrev'],
                name=livro['name'],
                num=num,
                texto=texto
            )
        else:
            return "Capítulo não encontrado.", 404
    else:
        return "Livro não encontrado.", 404

# Inicializador da aplicação
import os

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
