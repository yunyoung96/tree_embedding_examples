import subprocess
import sexpdata
from pathlib import Path
from dataclasses import dataclass, field
import os
import inspect
import json
import re
from datetime import datetime

from typing import Any

def require_not_none(obj, *field_names: str) -> None:
    for field_name in field_names:
        if getattr(obj, field_name) is None:
            raise ValueError(f"{obj.__class__.__name__}.{field_name} cannot be None")

def pretty_print_ast(ast, indent=0):
    prefix = "  " * indent
    if isinstance(ast, list):
        print(f"{prefix}[")
        for item in ast:
            pretty_print_ast(item, indent + 1)
        print(f"{prefix}]")
    elif isinstance(ast, sexpdata.Symbol):
        print(f"{prefix}{ast.value()}")
    else:
        print(f"{prefix}{repr(ast)}")

@dataclass
class SrcPos:
    line: int
    col: int

    def __post_init__(self):
        require_not_none(self, "line", "col")

    @property
    def column(self) -> int:
        return self.col

@dataclass
class SrcSpan:
    start: SrcPos
    end: SrcPos

    def __post_init__(self):
        require_not_none(self, "start", "end")

    def srcspantotuple(self) -> tuple[int, int, int, int]:
        return (self.start.line, self.start.col, self.end.line, self.end.col)

@dataclass
class AstInfo:
    sid: int
    ast: Any
    node_count: int
    depth: int
    tactic: str
    span: SrcSpan

    def __post_init__(self):
        require_not_none(self, "sid", "ast", "node_count", "depth", "tactic", "span")

@dataclass
class ProofWithAst:
    thm_stmt: str
    steps: list[str]
    thm_span: SrcSpan
    astinfo_for_thm: AstInfo
    astinfos_for_tactics: list[AstInfo] = field(default_factory=list)

    def __post_init__(self):
        require_not_none(
            self,
            "thm_stmt",
            "steps",
            "thm_span",
            "astinfo_for_thm",
            "astinfos_for_tactics",
        )

@dataclass
class ParseTarget:
    file_path: Path
    project_path: Path | None = None
    relative_file_path: Path | None = None

    def format_for_display(self) -> str:
        parts = [f"file={self.file_path}"]
        if self.relative_file_path is not None:
            parts.append(f"relative={self.relative_file_path}")
        if self.project_path is not None:
            parts.append(f"project={self.project_path}")
        return " | ".join(parts)

def format_src_span(span: SrcSpan) -> str:
    if span is None:
        raise ValueError("Cannot format a missing source span")
    return f"{span.start.line}:{span.start.col}-{span.end.line}:{span.end.col}"

def extract_text_by_span(source: str, span: SrcSpan) -> str:
    if span is None:
        raise ValueError("Cannot extract text from a missing source span")

    lines = source.splitlines()
    if span.start.line < 0:
        raise ValueError(f"Span start line is negative: {span.start.line}")
    if span.end.line < span.start.line:
        raise ValueError(f"Span end line is before start line: {format_src_span(span)}")
    if span.start.line >= len(lines):
        raise ValueError(f"Span start line is out of range: {span.start.line} >= {len(lines)}")
    if span.end.line >= len(lines):
        raise ValueError(f"Span end line is out of range: {span.end.line} >= {len(lines)}")

    if span.start.line == span.end.line:
        return lines[span.start.line][span.start.col:span.end.col]

    parts = [lines[span.start.line][span.start.col:]]
    parts.extend(lines[line_no] for line_no in range(span.start.line + 1, span.end.line))
    parts.append(lines[span.end.line][:span.end.col])
    return "\n".join(parts)

def sanitize_filename_part(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    return value.strip("_") or "unknown"

def proof_name_from_statement(thm_stmt: str) -> str:
    tokens = thm_stmt.strip().split()
    if len(tokens) >= 2:
        return tokens[1].rstrip(":")
    if tokens:
        return tokens[0].rstrip(":")
    return "unknown_proof"

def sexpdata_to_plain(obj):
    if isinstance(obj, sexpdata.Symbol):
        return obj.value()
    if isinstance(obj, list):
        return [sexpdata_to_plain(item) for item in obj]
    return obj

def ast_record_to_string(info: AstInfo) -> str:
    return repr([
        info.sid,
        sexpdata_to_plain(info.ast),
        info.node_count,
        info.depth,
        info.tactic,
    ])

def build_ast_results(
    proofs: list[ProofWithAst],
    file_path: str | Path,
    project_path: str | Path,
) -> dict[str, dict[str, dict[str, dict[str, str | list[str]]]]]:
    parse_target = Parser.extract_parse_target(file_path, project_path)
    project_name = parse_target.project_path.name if parse_target.project_path else "project"
    file_name = str(parse_target.relative_file_path or parse_target.file_path.name)

    proof_results: dict[str, dict[str, str | list[str]]] = {}
    for proof in proofs:
        proof_name = proof_name_from_statement(proof.thm_stmt)
        proof_results[proof_name] = {
            "astinfo_for_thm": ast_record_to_string(proof.astinfo_for_thm),
            "astinfos_for_tactics": [
                ast_record_to_string(info)
                for info in proof.astinfos_for_tactics
            ],
        }

    return {project_name: {file_name: proof_results}}

def save_ast_results(
    proofs: list[ProofWithAst],
    file_path: str | Path,
    project_path: str | Path,
    results_root: str | Path | None = None,
) -> Path:
    parse_target = Parser.extract_parse_target(file_path, project_path)
    project_name = parse_target.project_path.name if parse_target.project_path else "project"
    file_name = parse_target.file_path.name

    if results_root is None:
        results_root = Path(__file__).resolve().parent / "results"

    date_dir = Path(results_root) / datetime.now().strftime("%Y-%m-%d")
    date_dir.mkdir(parents=True, exist_ok=True)

    output_name = (
        f"ast_{sanitize_filename_part(project_name)}_"
        f"{sanitize_filename_part(file_name)}.json"
    )
    output_path = date_dir / output_name
    output_data = build_ast_results(proofs, file_path, project_path)
    output_path.write_text(
        json.dumps(output_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return output_path

@dataclass
class AddedSpan:
    sid: int
    start: SrcPos
    end: SrcPos
    snippet: str

    @property
    def span(self) -> SrcSpan:
        return SrcSpan(self.start, self.end)

class AddedSpanMap:
    def __init__(self, spans: list[AddedSpan] | None = None, print_flag: bool = False):
        self.spans = spans or []
        self._by_sid = {span.sid: span for span in self.spans}
        self.print_flag = print_flag

    def _print(self, *args, **kwargs):
        if self.print_flag:
            print(*args, **kwargs)

    @staticmethod
    def loc_list_to_dict(loc_list) -> dict:
        loc = {}
        for pair in loc_list:
            if isinstance(pair, list) and len(pair) == 2 and hasattr(pair[0], "value"):
                loc[pair[0].value()] = pair[1]
        return loc

    @staticmethod
    def offset_to_line_col(text: str, byte_offset: int) -> tuple[int, int]:
        text_bytes = text.encode("utf-8")
        byte_offset = max(0, min(byte_offset, len(text_bytes)))
        prefix = text_bytes[:byte_offset].decode("utf-8", errors="ignore")

        line = prefix.count("\n")
        line_start = prefix.rfind("\n")
        if line_start == -1:
            col = len(prefix)
        else:
            col = len(prefix) - line_start - 1
        return line, col

    @classmethod
    def get_span(
        cls,
        parsed,
        coq_code: str,
        print_flag: bool = False,
    ) -> "AddedSpanMap":
        span_map = cls(print_flag=print_flag)
        for item in parsed:
            if item[0].value() == "Feedback":
                continue
            if item[0].value() == "Answer" and len(item) >= 3:
                answer_content = item[2]
                if isinstance(answer_content, list) and len(answer_content) >= 2:
                    if answer_content[0].value() == "Added":
                        state_id = answer_content[1]
                        span_map._print(f"[DEBUG get_span input] raw item={item}")
                        span_map._print(f"[DEBUG get_span input] answer_content={answer_content}")
                        loc = cls.loc_list_to_dict(answer_content[2] if len(answer_content) >= 3 else [])
                        span_map._print(f"[DEBUG loc] sid={state_id} loc={loc}")
                        bp = int(loc.get("bp", 0))
                        ep = int(loc.get("ep", 0))
                        start_line, start_col = cls.offset_to_line_col(coq_code, bp)
                        end_line, end_col = cls.offset_to_line_col(coq_code, ep)

                        code_bytes = coq_code.encode("utf-8")
                        bp_clamped = max(0, min(bp, len(code_bytes)))
                        ep_clamped = max(0, min(ep, len(code_bytes)))
                        snippet = code_bytes[bp_clamped:ep_clamped].decode("utf-8", errors="replace").replace("\n", "\\n")

                        added_span = AddedSpan(
                            sid=state_id,
                            start=SrcPos(start_line, start_col),
                            end=SrcPos(end_line, end_col),
                            snippet=snippet,
                        )
                        span_map._print(f"[DEBUG AddedSpan add] {added_span}")
                        span_map._print("-" * 80)
                        span_map.add(added_span)
        return span_map

    def add(self, span: AddedSpan):
        self.spans.append(span)
        self._by_sid[span.sid] = span

    @property
    def state_ids(self) -> list[int]:
        return [span.sid for span in self.spans]

    def get_span_by_sid(self, sid: int) -> SrcSpan | None:
        span = self._by_sid.get(sid)
        if span is None:
            caller = inspect.stack()[1]
            raise ValueError(
                f"Span not found for sid {sid} "
                f"(called from {caller.filename}:{caller.lineno} in {caller.function})"
            )
        return span.span

    def get_snippet_by_sid(self, sid: int, default: str) -> str:
        def normalize_space(s):
            return " ".join(s.replace("\\n", " ").strip().split())

        import re
        span = self._by_sid.get(sid)
        tactic = span.snippet
        self._print(f"[DEBUG get_snippet_by_sid] before normalization: <{tactic}>")
        if tactic != default:
            tactic = str(tactic)
            tactic = tactic.replace('\\n', ' ').replace('\n', ' ')
            tactic_norm = re.sub(r'\s+', ' ', tactic).strip()
            self._print(f"[DEBUG get_snippet_by_sid] after normalization: <{tactic_norm}>")
            return tactic_norm
        self._print(f"[DEBUG get_snippet_by_sid] after normalization: <{tactic}>")
        return normalize_space(tactic)

class Parser:
    # Sentinel value for missing tactics
    _TACTIC_NOT_FOUND = "__NOT_FOUND__"
    
    def __init__(self, print_flag=False):
        self.print_flag = print_flag
        self.current_parse_target: ParseTarget | None = None

    @staticmethod
    def _resolve_path(path: str | Path | None) -> Path | None:
        if path is None:
            return None
        parsed_path = Path(path).expanduser()
        if not parsed_path.is_absolute():
            parsed_path = Path.cwd() / parsed_path
        return parsed_path.resolve(strict=False)

    @classmethod
    def extract_parse_target(
        cls,
        file_path: str | Path,
        project_path: str | Path | None = None,
    ) -> ParseTarget:
        resolved_file_path = cls._resolve_path(file_path)
        resolved_project_path = cls._resolve_path(project_path)
        assert resolved_file_path is not None

        relative_file_path = None
        if resolved_project_path is not None:
            try:
                relative_file_path = resolved_file_path.relative_to(resolved_project_path)
            except ValueError:
                relative_file_path = None

        return ParseTarget(
            file_path=resolved_file_path,
            project_path=resolved_project_path,
            relative_file_path=relative_file_path,
        )

    def get_current_parse_file_path(self) -> Path:
        if self.current_parse_target is None:
            raise ValueError("No file is currently being parsed")
        return self.current_parse_target.file_path

    def show_current_parse_target(self) -> str:
        if self.current_parse_target is None:
            raise ValueError("No file is currently being parsed")
        message = f"[Parser] Current parse target: {self.current_parse_target.format_for_display()}"
        print(message)
        return message
    
    @staticmethod
    def remove_coq_block_comments(text):
        # Coq comments can be nested: (* outer (* inner *) outer *)
        result = []
        depth = 0
        i = 0
        while i < len(text):
            if i + 1 < len(text) and text[i] == '(' and text[i + 1] == '*':
                depth += 1
                i += 2
                continue
            if depth > 0 and i + 1 < len(text) and text[i] == '*' and text[i + 1] == ')':
                depth -= 1
                i += 2
                continue
            if depth == 0:
                result.append(text[i])
            i += 1
        return ''.join(result)

    @staticmethod
    def go(process, coq_script):
        stdout, stderr = process.communicate(input=coq_script, timeout=120)
        return stdout

    def _print(self, *args, **kwargs):
        """Print only if print_flag is True"""
        if self.print_flag:
            print(*args, **kwargs)
    
    def run_sertop_commands(self, file_path: str | Path, project_path: str | Path) -> list[ProofWithAst]:
        self.current_parse_target = self.extract_parse_target(file_path, project_path)
        self._print(f"[Parser] Current parse target: {self.current_parse_target.format_for_display()}")

        cmd = ["sertop", "--printer=sertop"]

        coq_project_path = Path(project_path) / "_CoqProject"
        if not coq_project_path.exists():
            self._print(f"Warning: _CoqProject file not found at {coq_project_path}")
            raise FileNotFoundError("_CoqProject file not found in current directory")
        
        content = coq_project_path.read_text().strip()
        tokens = content.split()
        i = 0
        while i < len(tokens):
            if tokens[i] in ("-R", "-Q") and i + 2 < len(tokens):
                physical_path = (Path(project_path) / tokens[i+1]).resolve()
                logical_path = tokens[i+2]
                cmd.extend([tokens[i], f"{physical_path},{logical_path}"])
                self._print("tokens: ", tokens[i:i+3])
                i += 3
            else:
                i += 1

        self._print("cmd : ", cmd)
        
        def get_coq_code(file_path: str | Path, normalize_space=False):
            self._print(f"Reading Coq code from: {file_path}")
            basic_v_path = Path(file_path)
            if normalize_space:
                import re
                coq_lines = []

                self._print(f"Reading Coq code from: {basic_v_path}")

                for line in basic_v_path.read_text(encoding="utf-8").splitlines():
                    line = re.sub(r"\s+", " ", line).strip()
                    self._print(f"Processing line: {line}")
                    coq_lines.append(line)

                coq_code = " ".join(coq_lines).strip()
                coq_code = self.remove_coq_block_comments(coq_code)
                assert "\n" not in coq_code, "coq_code should be flattened to one line"
                return coq_code
            else:
                coq_code = basic_v_path.read_text(encoding="utf-8")
                return coq_code

        self._print("======> stage a: Reading and Preprocessing Coq Code =====")

        coq_code = get_coq_code(file_path, normalize_space=False)

        self._print("======> stage a: Coq Code to be Added =====")
        
        #self._print("coq_code: ", coq_code)
        dumped = sexpdata.dumps(coq_code)

        self._print("======> stage a: Dumped Coq Code =====")
        #self._print("dumped: ", dumped)

        coq_script_thm = f"(Add () {dumped})\n"

        def run_sertop_with_script(script):
            # Setup environment with opam bin directory
            env = os.environ.copy()
            
            process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env
            )
            return self.go(process, script)
        
        def parse_sertop_output(stdout, erase_feedback_sertop_output = True):
            parsed_str = "(" + stdout + ")"
            parsed = sexpdata.loads(parsed_str)
            ret = []
            for item in parsed:
                if item[0].value() == "Feedback" and erase_feedback_sertop_output:
                    continue
                ret.append(item)
            return ret

        self._print("======> stage a: Running SERTOP with Add Command =====")

        stdout = run_sertop_with_script(coq_script_thm)

        self._print("======> stage b: SERTOP RAW OUTPUT (after Add) =====")

        parsed_str = "(" + stdout + ")"

        self._print("parsed_str: ", parsed_str)

        parsed = sexpdata.loads(parsed_str)

        self._print("======> stage c: Extracting Added State IDs and Spans =====")

        span_map = AddedSpanMap.get_span(
            parsed,
            coq_code,
            self.print_flag,
        )
        added_state_ids = span_map.state_ids

        self._print("\n===== Added Span Mapping (sid -> source span) =====")
        for row in span_map.spans:
            self._print(
                f"sid={row.sid} | start={row.start.line}:{row.start.col} "
                f"| end={row.end.line}:{row.end.col} "
                f"| text='{row.snippet}'"
            )

        self._print(f"\n===== All Added State IDs: {added_state_ids} =====")

        if not added_state_ids:
            self._print("Warning: No added state IDs found. Returning empty proofs list.")
            return []

        coq_script = coq_script_thm + f"(Exec {added_state_ids[-1]})"

        for id in added_state_ids:
            #self._print(f"Adding query for sid: {id}")
            coq_script += f"(Query ((sid {id}) (pp ((pp_format PpSer)))) Goals)"

        stdout = run_sertop_with_script(coq_script)

        self._print("===== SERTOP RAW OUTPUT =====")

        coqasts = []
        for idx, item in enumerate(parse_sertop_output(stdout, erase_feedback_sertop_output = True)):
            self._print("-" * 80)
            self._print("item: ", item)
            if not (isinstance(item, list) and len(item) >= 3):
                continue
            answer_content = item[2]
            if not (isinstance(answer_content, list) and len(answer_content) >= 2):
                continue
            if not hasattr(answer_content[0], "value") or answer_content[0].value() != "ObjList":
                continue
            obj_list = answer_content[1]
            if not isinstance(obj_list, list):
                continue

            self._print("[AST stage] ObjList item accepted")
            self._print(f"[AST vars] item_idx={idx}, item_answer_id={item[1]}, obj_list_len={len(obj_list)}")
            self._print(f"[AST vars] obj_list={obj_list}")

            sid_idx = item[1] - 2
            sid = added_state_ids[sid_idx]
            self._print("[AST stage] resolved ObjList answer to added state id")
            self._print(f"[AST vars] sid_idx={sid_idx}, sid={sid}, added_state_ids_len={len(added_state_ids)}")
            self._print(f"Processing item with sid={sid}")
            tactic = span_map.get_snippet_by_sid(sid, self._TACTIC_NOT_FOUND)
            self._print(f"Associated tactic for sid {sid}: <{tactic}>")
            if len(obj_list) == 0:
                self._print("[AST stage] empty ObjList")
                self._print("No AST returned for this sid, appending empty list")
                coqasts.append((sid, []))
                self._print(f"[AST vars] appended coqasts entry: sid={sid}, ast=[]")
                continue

            self._print("[AST stage] validating single ObjList entry")
            self._print(f"[AST vars] len(obj_list)={len(obj_list)}")
            assert len(obj_list) == 1

            self._print(f"AST returned for sid {sid}: ", obj_list[0])
            for obj_idx, obj in enumerate(obj_list):
                self._print("[AST stage] processing ObjList entry")
                self._print(f"[AST vars] sid={sid}, obj_idx={obj_idx}, obj={obj}")
                if isinstance(obj, list) and len(obj) >= 1 and hasattr(obj[0], "value") and \
                    (obj[0].value() == "CoqAst" or obj[0].value() == "CoqGoal"):
                    self._print("[AST stage] recognized CoqAst/CoqGoal object")
                    self._print(f"[AST vars] obj_head={obj[0].value()}, obj_len={len(obj)}")
                    assert len(obj) == 2

                    goals = obj[1][0][1]
                    self._print("[AST stage] extracted goals")
                    self._print(f"[AST vars] goals_len={len(goals)}, goals={goals}")
                    goals_ty = []
                    
                    for goal_idx, goal in enumerate(goals):
                        self._print("[AST stage] processing goal")
                        self._print(f"[AST vars] goal_idx={goal_idx}, goal={goal}")
                        ty = goal[1]
                        self._print(f"[AST vars] goal_idx={goal_idx}, ty={ty}")
                        goals_ty.append(ty)
                        self._print(f"[AST vars] goals_ty_len={len(goals_ty)}")
                        assert ty[0].value() == "ty"

                    coqasts.append((sid, goals_ty))
                    self._print("[AST stage] appended parsed goals_ty")
                    self._print(f"[AST vars] appended sid={sid}, goals_ty={goals_ty}, coqasts_len={len(coqasts)}")
                else:
                    self._print("[AST stage] unrecognized object shape")
                    self._print(f"[AST vars] sid={sid}, obj_type={type(obj)}, obj={obj}")
        
        assert len(coqasts) == len(added_state_ids), f"Expected coqasts length to match added_state_ids length, but got {len(coqasts)} coqasts and {len(added_state_ids)} state IDs."

        def collect_ast_metrics(ast):
            if isinstance(ast, list):
                children = [collect_ast_metrics(item) for item in ast]
                processed_children = [c[0] for c in children]
                total_count = 1 + sum(c[1] for c in children)
                max_depth = max([c[2] for c in children]) if children else 0
                return (processed_children, total_count, max_depth + 1)
            return (ast, 1, 1)

        coqasts_light = [(sid, collect_ast_metrics(ast)) for sid, ast in coqasts]
        coqasts_proofs = []
        inner_proof = False

        self._print("before processing coqasts_light, len: ", len(coqasts_light))

        for node in coqasts_light:
            self._print("-" * 80)
            self._print("len of coqasts_proofs: ", len(coqasts_proofs))
            if len(coqasts_proofs) > 0:
                self._print("len of tactic astinfos: ", len(coqasts_proofs[-1][2]))
            sid, (ast, node_count, depth) = node
            self._print("sid while clustering proofs: ", sid)
            tactic = span_map.get_snippet_by_sid(sid, self._TACTIC_NOT_FOUND)
            if tactic == self._TACTIC_NOT_FOUND:
                self._print("[stage] skip: tactic not found")
                self._print(f"===> skipping sid: {sid}")
                continue
            self._print(f"===> candidate tactic: <{tactic}>")
            self._print(f"len of ast: len(ast)={len(ast)}")

            if (tactic.startswith('Proof') and inner_proof == False) \
                or (tactic.startswith('Proof using') and inner_proof == False):
                self._print("[stage] branch: proof-start")
                inner_proof = True
                raise RuntimeError(
                    "Proof start detected but no theorem/definition statement found. "
                    f"sid={sid}, tactic=<{tactic}>, ast={ast}"
                )

            if (tactic.startswith('Definition') and len(ast) != 0)\
                or (tactic.startswith('Let') and len(ast) != 0)\
                or (tactic.startswith('Theorem') and len(ast) != 0)\
                or (tactic.startswith('Lemma') and len(ast) != 0)\
                or (tactic.startswith('Next Obligation.') and len(ast) != 0)\
                or (tactic.startswith('Fixpoint') and len(ast) != 0)\
                or (tactic.startswith('Instance') and len(ast) != 0)\
                or (tactic.startswith('Global Instance') and len(ast) != 0)\
                or (tactic.startswith('Goal') and len(ast) != 0)\
                or (tactic.startswith('Remark') and len(ast) != 0)\
                or (tactic.startswith('Corollary') and len(ast) != 0)\
                or (tactic.startswith('Function') and len(ast) != 0)\
                or (tactic.startswith('Fact') and len(ast) != 0)\
                or (tactic.startswith('Example') and len(ast) != 0)\
                or (tactic.startswith('Proposition') and len(ast) != 0)\
                or (tactic.startswith('Add Morphism') and len(ast) != 0)\
                or (tactic.startswith('Add Parametric Morphism') and len(ast) != 0)\
                or (tactic.startswith('Derive') and len(ast) != 0)\
                :
                self._print("[stage] branch: theorem/definition-start")
                inner_proof = True
                thm_span = span_map.get_span_by_sid(sid)
                assert thm_span is not None, f"Theorem span not found for sid {sid}"
                astinfo_for_thm = AstInfo(sid, ast, node_count, depth, tactic, thm_span)
                coqasts_proofs.append((tactic, astinfo_for_thm, [], thm_span))
                self._print("===> new proof added with theorem span: ", format_src_span(thm_span))
                self._print(f"===> tactic : <{tactic}>")
                continue

            if inner_proof:
                self._print("[stage] branch: inside-proof")
                span = span_map.get_span_by_sid(sid)
                assert span is not None, f"Span not found for sid {sid}"
                assert isinstance(span, SrcSpan), f"Span should be a SrcSpan, but got {span} for sid {sid}"
                assert isinstance(span.start, SrcPos) and isinstance(span.end, SrcPos), f"Span should contain SrcPos values, but got {span} for sid {sid}"
                assert type(span.start.line) == int and type(span.start.col) == int, f"Span start should contain integers, but got {span.start} for sid {sid}"
                assert type(span.end.line) == int and type(span.end.col) == int, f"Span end should contain integers, but got {span.end} for sid {sid}"
                info = AstInfo(sid, ast, node_count, depth, tactic, span)
                if tactic.startswith('Ltac') or tactic.startswith('Local Ltac'):
                    self._print("[stage] branch: skip-ltac")
                    continue
                coqasts_proofs[-1][2].append(info)
                self._print("===> tactic : ", tactic)
            pattern = r"\s*Proof\s*\."
            import re
            if tactic in ['Qed.', 'Admitted.','Defined.'] \
                or (tactic.startswith('Proof ') 
                     and not tactic.startswith('Proof with ')
                     and not tactic.startswith('Proof using')
                     and not re.fullmatch(pattern, tactic)
                     ):
                self._print("[stage] branch: proof-end")
                inner_proof = False
            self._print()

        self._print("len of coqasts_proofs after processing: ", len(coqasts_proofs))
        for idx, proof_tuple in enumerate(coqasts_proofs):
            self._print(f"===> proof with tactics: idx: {idx}")
            thm_stmt, astinfo_for_thm, infos, thm_span = proof_tuple
            self._print(f"\tthm_stmt='{thm_stmt.strip()}'")
            self._print(f"\tthm_span={thm_span}")
            self._print(f"\tthm_ast_sid={astinfo_for_thm.sid}")
            for info in infos:
                self._print(f"\ttactic='{info.tactic.strip()}' with sid={info.sid}")
            self._print()

        # Convert to Proof objects
        proofs_list = []
        for idx, (thm_stmt, astinfo_for_thm, infos, thm_span) in enumerate(coqasts_proofs):
            self._print(
                "[run_sertop_commands] coqasts_proofs "
                f"idx={idx}, thm_span={format_src_span(thm_span)}, "
                f"thm_stmt=<{thm_stmt.strip()}>, tactic_count={len(infos)}"
            )
            if thm_span is None:
                raise RuntimeError(
                    "[run_sertop_commands] Missing theorem span in coqasts_proofs "
                    f"idx={idx}, thm_stmt=<{thm_stmt.strip()}>, tactic_count={len(infos)}"
                )
            steps = [info.tactic for info in infos]
            proofs_list.append(
                ProofWithAst(
                    thm_stmt=thm_stmt,
                    steps=steps,
                    thm_span=thm_span,
                    astinfo_for_thm=astinfo_for_thm,
                    astinfos_for_tactics=infos,
                )
            )

        return proofs_list

def main(file_path, project_path):
    print("(simple) Running SERTOP commands for a single file and printing results")
    print(f"(simple) Parse target: {Parser.extract_parse_target(file_path, project_path).format_for_display()}")

    parser = Parser(print_flag=True)
    proofs = parser.run_sertop_commands(file_path, project_path)
    output_path = save_ast_results(proofs, file_path, project_path)
    print(f"(simple) AST results saved to: {output_path}")
    coq_code = Path(file_path).read_text(encoding="utf-8")

    def print_proofs(proofs):
        print(">" * 40 + "pt2")
        print("\n" + "="*80)
        print("===== Proofs Summary =====")
        print("="*80)

        for proof in proofs:
            print("=" * 80)
            print(f"theorem/definition: <{proof.thm_stmt.strip()}>")
            print(f"theorem span: {format_src_span(proof.thm_span)}")
            print(f"theorem from span: <{extract_text_by_span(coq_code, proof.thm_span).strip()}>")
            print("Theorem AST:")
            pretty_print_ast(proof.astinfo_for_thm.ast, indent=2)
            print(f"Number of steps: {len(proof.steps)}")
            for idx, info in enumerate(proof.astinfos_for_tactics):
                print("-" * 80)
                print(f"Step {idx} span: {format_src_span(info.span)}")
                print(f"Step {idx} stored: <{info.tactic.strip()}>")
                print(f"Step {idx} from span: <{extract_text_by_span(coq_code, info.span).strip()}>")
                print(f"Step {idx} AST:")
                pretty_print_ast(info.ast, indent=2)

    print_proofs(proofs)

if __name__ == "__main__":
    repo_root = Path(__file__).resolve().parent

    paths = [
        (repo_root / "library" / "basic2.v", repo_root / "library"),
    ]

    idx = 0

    file_path = paths[idx][0]
    project_path = paths[idx][1]
    main(file_path=file_path, project_path=project_path)
