#!/usr/bin/env python3
"""
Generate batch prompt for proving theorems in basic2.v using LLM.
Extracts all theorems from basic2.v and creates a batch proof prompt.
Uses parser.SrcPos, parser.SrcSpan structures from parser.py.
"""

import re
import logging
from pathlib import Path
from dataclasses import dataclass

# Import from parser.py (requires activated virtual environment with sexpdata)
from parser import SrcPos, SrcSpan

# Setup logging - console only
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


@dataclass
class ProofWithSpan:
    """Proof representation with span information."""
    thm_stmt: str
    thm_span: SrcSpan
    tactic_spans: list[SrcSpan]


def src_pos_to_offset(source: str, pos) -> int:
    """Convert SrcPos to byte offset in source code."""
    lines = source.splitlines(keepends=True)
    if pos.line < 0 or pos.line >= len(lines):
        raise ValueError(f"Source line out of range: {pos.line}")
    return sum(len(line) for line in lines[:pos.line]) + pos.col


def extract_theorems_from_coq(coq_code: str) -> list[ProofWithSpan]:
    """Extract all theorems from Coq code."""
    # Pattern to match theorem/lemma/proposition/corollary/remark statements
    # Matches keywords and captures everything until "Proof." or a new definition
    theorem_keywords = r"(?:Lemma|Theorem|Proposition|Corollary|Remark)"
    
    proofs = []
    lines = coq_code.splitlines(keepends=True)
    
    # Find all theorem declarations
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # Look for theorem keyword
        match = re.search(theorem_keywords, line)
        if not match:
            i += 1
            continue
        
        start_line = i
        start_col = match.start()
        
        # Collect theorem statement until we find "Proof." or ":="
        theorem_lines = [line[match.start():]]
        i += 1
        
        while i < len(lines):
            current_line = lines[i]
            theorem_lines.append(current_line)
            
            # Stop at Proof., Defined., Admitted., or := (for definitions)
            if "Proof." in current_line or "Defined." in current_line or "Admitted." in current_line:
                # Remove the Proof./Defined./Admitted. part from the statement
                idx = max(
                    current_line.rfind("Proof."),
                    current_line.rfind("Defined."),
                    current_line.rfind("Admitted.")
                )
                if idx >= 0:
                    theorem_lines[-1] = current_line[:idx]
                break
            elif ":=" in current_line:
                break
                
            i += 1
        
        # Join theorem statement
        thm_stmt = "".join(theorem_lines).strip()
        
        # Only include if we have a valid statement
        if not thm_stmt.endswith(".") and not thm_stmt.endswith(":="):
            thm_stmt += "."
        
        end_line = i
        end_col = len(lines[end_line].rstrip())
        
        # Create span
        span = SrcSpan(
            start=SrcPos(line=start_line, col=start_col),
            end=SrcPos(line=end_line, col=end_col)
        )
        
        proof = ProofWithSpan(
            thm_stmt=thm_stmt,
            thm_span=span,
            tactic_spans=[]
        )
        proofs.append(proof)
        i += 1
    
    return proofs



def proof_label(proof: ProofWithSpan) -> str:
    """Generate span comment + theorem statement."""
    if proof.thm_span is None:
        raise ValueError(f"Proof {proof.thm_stmt} does not have theorem span")
    return f"(* {proof.thm_span.srcspantotuple()} *)\n{proof.thm_stmt}"


def replace_all_proofs_in_code(coq_code: str) -> str:
    """Replace all proofs (Proof...Qed/Defined/Admitted) with placeholder."""
    # Pattern to match Proof. followed by anything until Qed., Defined., or Admitted.
    pattern = r'Proof\.\s*.*?(?:Qed|Defined|Admitted)\.'
    result = re.sub(pattern, '...', coq_code, flags=re.DOTALL)
    return result


class PromptBuilder:
    """Build batch proof generation prompts from extracted theorems."""
    
    BATCH_DELIMITER = "<COQ_BATCH_PROOF_7f3b9c1d>"
    
    def __init__(self, proofs: list[ProofWithSpan], file_path: str | Path):
        """Initialize PromptBuilder with theorems and file path.
        
        Args:
            proofs: List of ProofWithSpan objects extracted from Coq code
            file_path: Path to the Coq source file
        """
        self.proofs = proofs
        self.file_path = Path(file_path)
        # Read and preprocess the Coq code from file
        self.coq_code = self.file_path.read_text(encoding="utf-8")
        self.code_for_hint = replace_all_proofs_in_code(self.coq_code)
    
    def build(self, tactics_limit: int = 0) -> str:
        """Build the batch proof generation prompt.
        
        Args:
            tactics_limit: Maximum number of tactics per proof (0 = no limit)
        
        Returns:
            Complete prompt string for LLM
        """
        theorems_with_span_comments = "\n\n".join(proof_label(proof) for proof in self.proofs)
        first_theorem = proof_label(self.proofs[0]).strip()
        
        tactic_limit_constraint = (
            f"Prefer concise proof scripts with no more than about {tactics_limit} tactic commands each when possible.\n"
            if tactics_limit > 0
            else ""
        )
        
        code_hint = (
            f"in the code:\n{self.code_for_hint}\n"
            "Use this code as a hint. The remaining span comments in this code hint are 0-based "
            "source spans for the requested target theorems, so you can use them to locate the target theorem positions.\n"
        )
        
        prompt_env = (
            "Environment:\n"
            "The Coq version is 8.18.\n"
        )
        
        prompt_to_do = (
            "Task:\n"
            "You have two inputs\n"
            "(1) The original coq code where the theorems are defined. The exact proofs are replaced with placeholders (...)\n"
            "where each target consists of a Coq comment with the source span in the original code and the theorem statement.\n"
            "(2) A list of multiple theorem/span targets to prove in the original code,"
            "You are completing multiple Coq proofs at once.\n"
            "Given input, you should generate proofs for all the theorem/span targets in the list, not just one.\n"
            "I am explaining the detailed formats for the input and the output:\n"
        )
        
        prompt_input = (
            "Input:\n"
            "Each target has a Coq comment containing the 0-based source span tuple "
            "(start line, start col, end line, end col),\n"
            "followed by the theorem statement. \n"
            f"{theorems_with_span_comments}\n"
            f"{code_hint}"
            f"There are exactly {len(self.proofs)} requested theorem(s) in the list above.\n"
            f"Return exactly {len(self.proofs)} theorem/proof block(s).\n"
            "Only prove the theorem/lemma statements listed immediately after 'Please solve the following theorem/span targets'.\n"
            "Use the span comment only to identify the target when names repeat. \n"
            "Do not prove, repeat, or output any other theorem/lemma that appears only in the code hint. \n"
            "For each theorem, output the exact source span comment from the list above,\n"
            "then output the theorem/lemma statement from the list above, then return the complete proof script. \n"
            "The proof script must include all proof commands after the theorem statement, including Proof.\n"
            "and the closing Qed. or Defined. when they are needed. \n"
            f"Your response must start immediately with this exact text: {first_theorem}\n"
            "Do not write any introduction such as 'Here are the proofs for each theorem:'. \n"
            "Do not add headings, bullet points, code fences, explanations, "
            "or any extra commentary before, between, or after the theorem/proof blocks. \n"
        )
        
        prompt_output = (
            "Output Format:\n"
            f"After every span comment plus theorem/lemma statement, output the exact delimiter {self.BATCH_DELIMITER} on its own line. \n"
            f"After every proof script, output the exact delimiter {self.BATCH_DELIMITER} on its own line. \n"
            "Use exactly this format for each theorem: \n"
            f"(* (0, 0, 0, 37) *)\nLemma true_and_true : True /\\ True.\n{self.BATCH_DELIMITER}\nProof.\n  split; exact I.\nQed.\n{self.BATCH_DELIMITER}\n"
            "Therefore, the number of delimiter lines in the output should be exactly twice the number of theorems in the input list.\n"
        )
        
        prompt_output_constraints = (
            "Output Constraints:\n"
            "Your entire response must be Coq text only, plus the delimiter lines described above.\n"
            "The first non-whitespace characters of your response must be the first requested source span comment.\n"
            "Do not output any natural-language text anywhere in the response.\n"
            "Forbidden examples include: 'Here are the proofs', 'Here is the proof', 'Below are the proofs', explanations, notes, apologies, or summaries.\n"
            "Do not use Markdown code fences, headings, bullet points, numbering, or prose labels.\n"
            "Do not reproduce, imitate, or rely on any memorized existing answer or original proof; "
            "derive each proof from the theorem statement, available context, and mathematical reasoning.\n"
            "Do not use the theorem currently being proved by name inside its own proof.\n"
            "Do not look up, access, or use any CompCert answers, original proofs, or proof solutions from the internet.\n"
            "Never use Admitted, admit, Abort, or any command/tactic that leaves proof obligations unsolved.\n"
            "Every proof must be fully completed with Qed. or Defined.\n"
            f"{tactic_limit_constraint}"
            "Use only tactics, lemmas, and notations that are available from Coq's default environment or\n"
            "from libraries already imported in the given code hint; "
            "Do not assume any extra Require Import, From Coq Require Import, or imported plugins.\n"
            "Output the requested source span comments exactly as shown. Do not output any other Coq comments. \n"
            "Do not rewrite, summarize, reformat, split, or add Markdown around the theorem/lemma statement. \n"
            "The statement must remain valid Coq syntax, including keywords, binders, colons, forall clauses, \n"
            "and the final period exactly as given. \n"
        )
        
        prompt_output_example = (
            "Output Example:\n"
            f"(* (0, 0, 0, 37) *)\n"
            f"Lemma true_and_true : True /\\ True.\n"
            f"{self.BATCH_DELIMITER}\n"
            f"Proof.\n"
            f"  split; exact I.\n"
            f"Qed.\n"
            f"{self.BATCH_DELIMITER}\n"
            f"(* (2, 0, 2, 63) *)\n"
            f"Lemma and_comm_simple : forall P Q : Prop, P /\\ Q -> Q /\\ P.\n"
            f"{self.BATCH_DELIMITER}\n"
            f"Proof.\n"
            f"  intros P Q H.\n"
            f"  destruct H as [HP HQ].\n"
            f"  split; assumption.\n"
            f"Qed.\n"
            f"{self.BATCH_DELIMITER}\n"
            f"(* (7, 0, 7, 61) *)\n"
            f"Lemma option_some_not_none : forall n : nat, Some n <> None.\n"
            f"{self.BATCH_DELIMITER}\n"
            f"Proof.\n"
            f"  intros n H.\n"
            f"  discriminate H.\n"
            f"Qed.\n"
            f"{self.BATCH_DELIMITER}\n"
        )
        
        prompts = [
            prompt_env,
            prompt_to_do,
            prompt_input,
            prompt_output,
            prompt_output_constraints,
            prompt_output_example,
        ]
        return "\n\n".join(prompts)



def main():
    """Main entry point."""
    file_path = Path(__file__).parent / "library" / "basic.v"
    
    logger.info(f"Reading {file_path}...")
    coq_code = file_path.read_text(encoding="utf-8")
    
    logger.info(f"Extracting theorems from basic2.v...")
    proofs = extract_theorems_from_coq(coq_code)
    
    if not proofs:
        logger.error("No proofs found!")
        return
    
    logger.info(f"Found {len(proofs)} theorems")
    
    # Build prompt using PromptBuilder class
    logger.info(f"Building batch prompt for {len(proofs)} theorems...")
    builder = PromptBuilder(proofs, file_path)
    prompt = builder.build()
    
    # Log prompt to console
    logger.info(f"Prompt length: {len(prompt)} characters")
    logger.info("="*80)
    logger.info("GENERATED BATCH PROMPT:")
    logger.info("="*80)
    logger.info(prompt)
    logger.info("="*80)


if __name__ == "__main__":
    main()

