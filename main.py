import json

with open('biblia.json', 'r', encoding='utf-8-sig') as f:
    biblia = json.load(f)

def buscar_versiculo(biblia, abbrev_livro, capitulo, versiculo):
    for livro in biblia:
        if livro['abbrev'].lower() == abbrev_livro.lower():
            try:
                texto_versiculo = livro['chapters'][capitulo - 1][versiculo - 1]
                return texto_versiculo
            except IndexError:
                return f"Capítulo {capitulo} ou versículo {versiculo} não encontrado."
    return f"Livro '{abbrev_livro}' não encontrado."

def interface():
    print("=== Consulta Bíblia ===")
    while True:
        abbrev = input("Digite a abreviação do livro (ex: gn) ou 'sair' para encerrar: ").strip()
        if abbrev.lower() == 'sair':
            print("Encerrando programa.")
            break
        capitulo = input("Digite o capítulo: ").strip()
        versiculo = input("Digite o versículo: ").strip()

        if not (capitulo.isdigit() and versiculo.isdigit()):
            print("Capítulo e versículo devem ser números inteiros.\n")
            continue

        capitulo = int(capitulo)
        versiculo = int(versiculo)

        resultado = buscar_versiculo(biblia, abbrev, capitulo, versiculo)
        print(f"\n{abbrev.upper()} {capitulo}:{versiculo} -> {resultado}\n")

if __name__ == "__main__":
    interface()
