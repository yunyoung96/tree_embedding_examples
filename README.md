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
