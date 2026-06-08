import subprocess
import sexpdata
from pathlib import Path
from dataclasses import dataclass, field
import os
import inspect
import json
import re
from datetime import datetime
from collections import Counter
from typing import Any, TypeAlias

try:
    from data_management.ast_types import Ast
    from data_management import tree_utils
except ImportError:
    from ast_types import Ast
    import tree_utils

AstMetric: TypeAlias = tuple[Ast | str, int, int]

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
    ast: Ast
    node_count: int
    depth: int
    tactic: str
    goal_string: str
    span: SrcSpan

    def __post_init__(self):
        require_not_none(self, "sid", "ast", "node_count", "depth", "tactic", "goal_string", "span")

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

    def all_astinfos(self) -> list[AstInfo]:
        return [self.astinfo_for_thm, *self.astinfos_for_tactics]

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
    assert isinstance(obj, (int, float, str)), (
        f"Expected int, float, or str in sexpdata_to_plain, got {type(obj).__name__}: {obj!r}"
    )
    return str(obj)

def ast_record_to_string(info: AstInfo) -> str:
    return repr([
        info.sid,
        info.ast,
        info.node_count,
        info.depth,
        info.tactic,
        info.goal_string,
    ])

def split_goal_string_blocks(goal_string: str) -> list[tuple[str, str]]:
    separator = "============================"
    if separator not in goal_string:
        return []

    parts = goal_string.split(separator)
    if len(parts) < 2:
        return []

    hyps = parts[0].strip("\n")
    blocks: list[tuple[str, str]] = []
    for idx, segment in enumerate(parts[1:], start=1):
        if idx < len(parts) - 1:
            if "\n\n" not in segment:
                return []
            conclusion, next_hyps = segment.rsplit("\n\n", 1)
        else:
            conclusion = segment
            next_hyps = None

        blocks.append((hyps.strip("\n"), conclusion.strip("\n")))
        if next_hyps is not None:
            hyps = next_hyps.strip("\n")

    return blocks

def normalize_goal_hyps(hyps: str) -> str:
    lines = [line.strip() for line in hyps.splitlines() if line.strip()]
    if len(lines) == 1 and lines[0] == "none":
        return ""
    return "\n".join(lines)

def format_goal_string_with_shared_hyps(goal_string: str) -> str:
    blocks = split_goal_string_blocks(goal_string)
    if len(blocks) <= 1:
        return goal_string

    normalized_hyps = [normalize_goal_hyps(hyps) for hyps, _conclusion in blocks]
    share_hyps = all(hyps == normalized_hyps[0] for hyps in normalized_hyps)

    lines: list[str] = []
    if share_hyps and normalized_hyps[0]:
        lines.extend(blocks[0][0].strip("\n").splitlines())

    total_goals = len(blocks)
    for idx, (hyps, conclusion) in enumerate(blocks, start=1):
        normalized_goal_hyps = normalized_hyps[idx - 1]
        if idx > 1:
            lines.extend(["", f"Goal {idx}", ""])
        if not share_hyps and normalized_goal_hyps:
            lines.extend(hyps.strip("\n").splitlines())
        lines.append(f"({idx} / {total_goals})")
        lines.extend(conclusion.splitlines() or [""])

    return "\n".join(lines)

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
    
    def __init__(self, print_flag: bool = False, include_hypothesis_asts: bool = False):
        self.print_flag = print_flag
        self.include_hypothesis_asts = include_hypothesis_asts
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

    @staticmethod
    def parse_sertop_output(stdout: str, erase_feedback_sertop_output: bool = True) -> list[Any]:
        parsed_str = "(" + stdout + ")"
        parsed = sexpdata.loads(parsed_str)
        ret = []
        for item in parsed:
            if item[0].value() == "Feedback" and erase_feedback_sertop_output:
                continue
            ret.append(item)
        return ret

    @staticmethod
    def sexp_field_tag(field: Any) -> str | None:
        if not (isinstance(field, list) and len(field) >= 1):
            return None
        tag = field[0]
        if hasattr(tag, "value"):
            return tag.value()
        if isinstance(tag, str):
            return tag
        return None

    @classmethod
    def sexp_field_is_empty_hyp(cls, field: Any) -> bool:
        return (
            cls.sexp_field_tag(field) == "hyp"
            and isinstance(field, list)
            and len(field) == 2
            and isinstance(field[1], list)
            and len(field[1]) == 0
        )

    @classmethod
    def extract_goal_ast_fields(cls, goal: Any, include_hypothesis_asts: bool = False) -> list[Any]:
        assert isinstance(goal, list), (
            "Expected goal to be a list of fields, "
            f"but got goal={goal}"
        )

        ty = next(
            (field for field in goal if cls.sexp_field_tag(field) == "ty"),
            None,
        )
        assert ty is not None, (
            "Expected goal to include a ty field, "
            f"but got goal={goal}"
        )

        goal_ast_fields = [ty]
        if include_hypothesis_asts:
            hyp = next(
                (field for field in goal if cls.sexp_field_tag(field) == "hyp"),
                None,
            )
            if hyp is not None and not cls.sexp_field_is_empty_hyp(hyp):
                goal_ast_fields.append(hyp)

        return goal_ast_fields

    def run_sertop_with_script(self, file_path: str | Path, project_path: str | Path, script: str) -> str:
        cmd = ["sertop", "--printer=sertop"]
        # Setup environment with opam bin directory

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
        env = os.environ.copy()
        
        process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
            cwd=project_path,
        )
        return self.go(process, script)

    def get_coq_code(self, file_path: str | Path, normalize_space: bool = False) -> str:
        self._print(f"Reading Coq code from: {file_path}")
        basic_v_path = Path(file_path)
        if normalize_space:
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

    def get_coq_goals(
        self,
        file_path: str | Path,
        project_path: str | Path,
        coq_script_thm: str,
        added_state_ids: list[int],
        span_map: AddedSpanMap,
    ) -> list[str]:
        self._print("(get_coq_goals) get_coq_goals is called")
        coq_script = coq_script_thm
        query_answer_ids: dict[int, int] = {}
        next_answer_id = 1
        for sid in added_state_ids:
            coq_script += f"(Exec {sid})"
            next_answer_id += 1
            query_answer_ids[next_answer_id] = sid
            coq_script += f"(Query ((sid {sid}) (pp ((pp_format PpStr)))) Goals)"
            next_answer_id += 1

        stdout = self.run_sertop_with_script(
            file_path=file_path,
            project_path=project_path,
            script=coq_script,
        )

        coq_goal_strings: list[str] = []
        for idx, item in enumerate(self.parse_sertop_output(stdout, erase_feedback_sertop_output=True)):
            self._print("-" * 80)
            self._print("(get_coq_goals) item: ", item)
            if not (isinstance(item, list) and len(item) >= 3):
                continue
            answer_id = item[1]
            if answer_id not in query_answer_ids:
                continue
            answer_content = item[2]
            assert not (
                isinstance(answer_content, list)
                and len(answer_content) >= 1
                and hasattr(answer_content[0], "value")
                and answer_content[0].value() == "CoqExn"
            ), (
                "PpStr Goals query failed even after executing to the queried sid. "
                f"answer_id={answer_id}, sid={query_answer_ids[answer_id]}, answer_content={answer_content}"
            )
            if not (isinstance(answer_content, list) and len(answer_content) >= 2):
                continue
            if not hasattr(answer_content[0], "value") or answer_content[0].value() != "ObjList":
                continue
            obj_list = answer_content[1]
            if not isinstance(obj_list, list):
                continue

            self._print("[Goal stage] ObjList item accepted")
            self._print(f"[Goal vars] item_idx={idx}, item_answer_id={answer_id}, obj_list_len={len(obj_list)}")
            self._print(f"[Goal vars] obj_list={obj_list}")

            sid = query_answer_ids[answer_id]
            self._print("[Goal stage] resolved ObjList answer to added state id")
            self._print(f"[Goal vars] sid={sid}, added_state_ids_len={len(added_state_ids)}")
            tactic = span_map.get_snippet_by_sid(sid, self._TACTIC_NOT_FOUND)
            self._print(f"Associated tactic for sid {sid}: <{tactic}>")

            if len(obj_list) == 0:
                coq_goal_strings.append("There are no more subgoals")
            else:
                obj = obj_list[0]
                self._print("[Goal stage] processing ObjList entry")
                self._print(f"[Goal vars] obj={obj}")

                assert len(obj_list) == 1, (
                    "Expected exactly one object in PpStr ObjList, "
                    f"but got {len(obj_list)} objects for sid={sid}, tactic=<{tactic}>, obj_list={obj_list}"
                )
                assert isinstance(obj, list) and len(obj) == 2, (
                    "Expected PpStr ObjList entry to be a two-element list, "
                    f"but got obj={obj} for sid={sid}, tactic=<{tactic}>"
                )

                obj_head, goal_string = obj
                assert hasattr(obj_head, "value") and obj_head.value() == "CoqString" and isinstance(goal_string, str), (
                    "Expected PpStr ObjList entry to have shape [CoqString, str], "
                    f"but got obj={obj} for sid={sid}, tactic=<{tactic}>"
                )

                coq_goal_strings.append(goal_string)
                self._print("[Goal stage] appended CoqString")
                self._print(
                    f"[Goal vars] goal_string={goal_string!r}, "
                    f"coq_goal_strings_len={len(coq_goal_strings)}"
                )

        return coq_goal_strings

    def get_coq_asts(
        self,
        file_path: str | Path,
        project_path: str | Path,
        coq_script_thm: str,
        added_state_ids: list[int],
        span_map: AddedSpanMap,
        include_hypothesis_asts: bool | None = None,
    ) -> list[tuple[int, AstMetric]]:
        self._print("(get_coq_asts) get_coq_asts is called")
        if include_hypothesis_asts is None:
            include_hypothesis_asts = self.include_hypothesis_asts
        coq_script = coq_script_thm + f"(Exec {added_state_ids[-1]})"
        for sid in added_state_ids:
            coq_script += f"(Query ((sid {sid}) (pp ((pp_format PpSer)))) Goals)"

        stdout = self.run_sertop_with_script(
            file_path=file_path,
            project_path=project_path,
            script=coq_script,
        )

        coqasts: list[tuple[int, Ast]] = []
        for idx, item in enumerate(self.parse_sertop_output(stdout, erase_feedback_sertop_output=True)):
            self._print("-" * 80)
            self._print("(get_coq_asts) item: ", item)
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
                    goals_ast = []

                    for goal_idx, goal in enumerate(goals):
                        self._print("[AST stage] processing goal")
                        self._print(f"[AST vars] goal_idx={goal_idx}, goal={goal}")
                        goal_ast_fields = self.extract_goal_ast_fields(
                            goal,
                            include_hypothesis_asts=include_hypothesis_asts,
                        )
                        ty = goal_ast_fields[0]
                        self._print(f"[AST vars] goal_idx={goal_idx}, ty={ty}")
                        assert self.sexp_field_tag(ty) == "ty"

                        if include_hypothesis_asts:
                            hyp = next(
                                (field for field in goal if self.sexp_field_tag(field) == "hyp"),
                                None,
                            )
                            if hyp is not None:
                                assert self.sexp_field_tag(hyp) == "hyp"
                                hyp_is_empty = self.sexp_field_is_empty_hyp(hyp)
                                self._print(f"[AST vars] goal_idx={goal_idx}, hyp={hyp}, hyp_is_empty={hyp_is_empty}")
                        goals_ast.extend(goal_ast_fields)
                        self._print(f"[AST vars] goals_ast_len={len(goals_ast)}")

                    plain_goals_ast = sexpdata_to_plain(goals_ast)

                    coqasts.append((sid, plain_goals_ast))
                    self._print("[AST stage] appended parsed goals_ast")
                    self._print(f"[AST vars] appended sid={sid}, goals_ast={plain_goals_ast}, coqasts_len={len(coqasts)}")
                else:
                    self._print("[AST stage] unrecognized object shape")
                    self._print(f"[AST vars] sid={sid}, obj_type={type(obj)}, obj={obj}")

        assert len(coqasts) == len(added_state_ids), f"Expected coqasts length to match added_state_ids length, but got {len(coqasts)} coqasts and {len(added_state_ids)} state IDs."

        def collect_ast_metrics(ast: Ast | str) -> AstMetric:
            if isinstance(ast, list):
                children = [collect_ast_metrics(item) for item in ast]
                processed_children = [c[0] for c in children]
                total_count = 1 + sum(c[1] for c in children)
                max_depth = max([c[2] for c in children]) if children else 0
                return (processed_children, total_count, max_depth + 1)
            return (ast, 1, 1)

        return [(sid, collect_ast_metrics(ast)) for sid, ast in coqasts]

    def run_sertop_commands(
        self,
        file_path: str | Path,
        project_path: str | Path,
        include_hypothesis_asts: bool | None = None,
    ) -> list[ProofWithAst]:
        if include_hypothesis_asts is None:
            include_hypothesis_asts = self.include_hypothesis_asts
        self.current_parse_target = self.extract_parse_target(file_path, project_path)
        self._print(f"[Parser] Current parse target: {self.current_parse_target.format_for_display()}")
        self._print(f"[Parser] Include hypothesis ASTs: {include_hypothesis_asts}")

        self._print("======> stage a: Reading and Preprocessing Coq Code =====")

        coq_code = self.get_coq_code(file_path, normalize_space=False)

        self._print("======> stage a: Coq Code to be Added =====")

        dumped = sexpdata.dumps(coq_code)

        self._print("======> stage a: Dumped Coq Code =====")

        coq_script_thm = f"(Add () {dumped})\n"
        
        self._print("======> stage a: Running SERTOP with Add Command =====")

        stdout = self.run_sertop_with_script(file_path=file_path, project_path=project_path, script=coq_script_thm)

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

        coqast_metrics = self.get_coq_asts(
            file_path=file_path,
            project_path=project_path,
            coq_script_thm=coq_script_thm,
            added_state_ids=added_state_ids,
            span_map=span_map,
            include_hypothesis_asts=include_hypothesis_asts,
        )

        coq_goal_strings = self.get_coq_goals(
            file_path=file_path,
            project_path=project_path,
            coq_script_thm=coq_script_thm,
            added_state_ids=added_state_ids,
            span_map=span_map,
        )
        self._print("before processing coq_goal_strings, len: ", len(coq_goal_strings))

        coqasts_proofs = []
        inner_proof = False

        theorem_like_prefixes = (
            "Definition",
            "Let",
            "Theorem",
            "Lemma",
            "Next Obligation.",
            "Fixpoint",
            "Instance",
            "Goal",
            "Remark",
            "Corollary",
            "Function",
            "Fact",
            "Example",
            "Proposition",
            "Add Morphism",
            "Add Parametric Morphism",
            "Derive",
        )
        theorem_like_qualifiers = (
            "",
            "Local ",
            "Global ",
            "Polymorphic ",
            "Global Polymorphic ",
            "Program ",
            "Local Program ",
            "Global Program ",
        )

        def is_theorem_like_start(tactic: str, ast: Ast | str) -> bool:
            if len(ast) == 0:
                return False
            normalized_tactic = " ".join(tactic.split())
            normalized_tactic = re.sub(r"^(?:#\[[^\]]+\]\s*)+", "", normalized_tactic)
            return any(
                normalized_tactic.startswith(f"{qualifier}{prefix}")
                for qualifier in theorem_like_qualifiers
                for prefix in theorem_like_prefixes
            )

        self._print("before processing coqast_metrics, len: ", len(coqast_metrics))

        assert len(coq_goal_strings) == len(coqast_metrics), (
            "Expected PpStr goal strings and PpSer AST metrics to align one-to-one, "
            f"but got {len(coq_goal_strings)} goal strings and {len(coqast_metrics)} AST metric entries. "
            "This usually means some queried sids returned an empty ObjList in one printer mode "
            "(for example Qed./closed-proof states) while the other mode still produced an entry. "
            f"added_state_ids={added_state_ids}, "
            f"coq_goal_strings={coq_goal_strings}, "
            f"coqast_metric_sids={[sid for sid, _ in coqast_metrics]}"
        )

        for node, goal_string in zip(coqast_metrics, coq_goal_strings):
            self._print("-" * 80)
            self._print("len of coqasts_proofs: ", len(coqasts_proofs))
            if len(coqasts_proofs) > 0:
                self._print("len of tactic astinfos: ", len(coqasts_proofs[-1][2]))
            sid, (ast, node_count, depth) = node
            self._print("sid while clustering proofs: ", sid)
            self._print(f"goal string while clustering proofs: <{goal_string}>")
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

            if is_theorem_like_start(tactic, ast):
                self._print("[stage] branch: theorem/definition-start")
                inner_proof = True
                thm_span = span_map.get_span_by_sid(sid)
                assert thm_span is not None, f"Theorem span not found for sid {sid}"
                astinfo_for_thm = AstInfo(sid, ast, node_count, depth, tactic, goal_string, thm_span)
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
                info = AstInfo(sid, ast, node_count, depth, tactic, goal_string, span)
                if tactic.startswith('Ltac') or tactic.startswith('Local Ltac'):
                    self._print("[stage] branch: skip-ltac")
                    continue
                coqasts_proofs[-1][2].append(info)
                self._print("===> tactic : ", tactic)
            pattern = r"\s*Proof\s*\."
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

def main(
    file_path,
    project_path,
    print_analysis: bool = False,
    include_hypothesis_asts: bool = False,
):
    print("(simple) Running SERTOP commands for a single file and printing results")
    print(f"(simple) Parse target: {Parser.extract_parse_target(file_path, project_path).format_for_display()}")
    print(f"(simple) Include hypothesis ASTs: {include_hypothesis_asts}")

    parser = Parser(print_flag=True)
    proofs = parser.run_sertop_commands(
        file_path,
        project_path,
        include_hypothesis_asts=include_hypothesis_asts,
    )
    output_path = save_ast_results(proofs, file_path, project_path)
    print(f"(simple) AST results saved to: {output_path}")

    def print_proofs(proofs, coq_code: str):
        def print_goal(label: str, goal_string: str) -> None:
            print(f"{label} goal: <")
            print(format_goal_string_with_shared_hyps(goal_string))
            print(">")

        def print_ast_with_filtering(
            label: str,
            ast: Ast | str,
            theorem_name: str,
            tactic: str,
        ) -> None:
            print(f"{label} theorem: <{theorem_name}>")
            print(f"{label} tactic: <{tactic.strip()}>")
            # print(f"{label} AST (before filtering):")
            # print(ast)
            print(f"{label} AST (after dfs_with_filtering):")
            filtered_tree = tree_utils.dfs_with_filtering(ast)
            tree_utils.pretty_print_tree(filtered_tree, indent=2)

        print(">" * 40 + "pt2")
        print("\n" + "="*80)
        print("===== Proofs Summary =====")
        print("="*80)

        for proof in proofs:
            theorem_name = proof_name_from_statement(proof.thm_stmt)
            print("=" * 80)
            print(f"theorem/definition: <{proof.thm_stmt.strip()}>")
            print(f"theorem span: {format_src_span(proof.thm_span)}")
            print(f"theorem from span: <{extract_text_by_span(coq_code, proof.thm_span).strip()}>")
            print_goal("theorem", proof.astinfo_for_thm.goal_string)
            print_ast_with_filtering(
                "Theorem",
                proof.astinfo_for_thm.ast,
                theorem_name,
                proof.astinfo_for_thm.tactic,
            )
            print(f"Number of steps: {len(proof.steps)}")
            for idx, info in enumerate(proof.astinfos_for_tactics):
                print("-" * 80)
                print(f"Step {idx} span: {format_src_span(info.span)}")
                print(f"Step {idx} stored: <{info.tactic.strip()}>")
                print(f"Step {idx} from span: <{extract_text_by_span(coq_code, info.span).strip()}>")
                print_goal(f"Step {idx}", info.goal_string)
                print_ast_with_filtering(
                    f"Step {idx}",
                    info.ast,
                    theorem_name,
                    info.tactic,
                )

    def print_nearest_astinfos_by_source(proofs, top_k=5, q=2):
        def format_indented_block(value, indent: str) -> str:
            text = str(value)
            return "\n".join(f"{indent}{line}" for line in text.splitlines() or [""])

        branch_records = []
        for proof in proofs:
            proof_name = proof_name_from_statement(proof.thm_stmt)
            for astinfo_idx, info in enumerate(proof.all_astinfos()):
                role = "theorem" if astinfo_idx == 0 else f"tactic[{astinfo_idx - 1}]"
                tree = tree_utils.dfs_with_filtering(info.ast)
                branches = tree_utils.extract_q_level_binary_branches(tree, q=q)
                branch_records.append(
                    {
                        "proof_name": proof_name,
                        "thm_stmt": proof.thm_stmt,
                        "role": role,
                        "info": info,
                        "tree": tree,
                        "branches": branches,
                        "vector": Counter(branches),
                    }
                )

        print("\n" + "=" * 80)
        print(f"===== Per-AstInfo Top {top_k} Nearest Neighbors by Branch Distance =====")
        print("=" * 80)

        for source_idx, source in enumerate(branch_records):
            source_info = source["info"]
            neighbors = []
            for target_idx, target in enumerate(branch_records):
                if source_idx == target_idx:
                    continue
                normalized_dist, raw_dist = tree_utils.compute_branch_distance_from_vectors(
                    source["vector"],
                    target["vector"],
                    q=q,
                )
                neighbors.append(
                    (
                        normalized_dist,
                        raw_dist,
                        target,
                    )
                )

            print("-" * 80)
            print(f"Source theorem: {source['proof_name']}")
            print(f"Source tactic : <{source_info.tactic.strip()}>")
            print(f"Source goal   : <{source_info.goal_string}>")
            print(f"Source branches: {source['branches']}")
            neighbors.sort(key=lambda item: (item[0], item[1]))
            for rank, (_normalized_dist, _raw_dist, target) in enumerate(neighbors[:top_k], start=1):
                target_info = target["info"]
                print(f"  top{rank}. theorem: {target['proof_name']}")
                print(f"     tactic  : <{target_info.tactic.strip()}>")
                print("     goal    :")
                print(format_indented_block(target_info.goal_string, "       "))
                print("     branches:")
                print(format_indented_block(target["branches"], "       "))


    coq_code = Path(file_path).read_text(encoding="utf-8")
    print_proofs(proofs, coq_code)
    if print_analysis:
        print_nearest_astinfos_by_source(proofs)


if __name__ == "__main__":
    repo_root = Path(__file__).resolve().parent

    paths = [
        (repo_root / "library" / "simple.v", repo_root / "library"),
    ]

    idx = 0

    file_path = paths[idx][0]
    project_path = paths[idx][1]
    main(file_path=file_path, project_path=project_path)
