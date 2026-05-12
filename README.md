# tree_embedding_examples

## Requirements

- Python package: install dependencies with `pip install -r requirements.txt`.
- Coq: use Coq 8.18.

Install Coq 8.18 and SerAPI with opam:

```bash
opam switch create coq-8.18 ocaml-base-compiler.4.14.1
eval $(opam env --switch=coq-8.18)
opam install coq.8.18.0 coq-serapi.8.18.0+0.18.3
coqc --version
```

## Usage

Parse the Coq file and write AST JSON results:

```bash
python parser.py
```

`parser.py` currently parses `library/basic2.v`. It saves JSON files under `results/<YYYY-MM-DD>/` with names like:

```text
results/2026-05-12/ast_library_basic2.v.json
```

The JSON format is `project -> file -> theorem -> AST step strings`, matching `analysis_from_RANGO/ast_basic2.json`.

Run the RANGO analysis/pretty-printer with the default JSON:

```bash
python analysis_from_RANGO/main.py
```

By default, it reads:

```text
analysis_from_RANGO/ast_basic2.json
```

To use another JSON file, pass its path. Example:

```bash
python analysis_from_RANGO/main.py Example.json
```

Replace the example json path

`analysis_from_RANGO/main.py` currently prints the filtered structural AST with theorem names and tactics.
