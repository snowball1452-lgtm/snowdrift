"""
Ghidra Analyzer — Deep reverse engineering & code analysis
Analyzes code structure, finds patterns, decompiles logic, understands architecture.
Like Ghidra but for understanding your codebase from the inside out.
"""

import os
import json
import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional, Dict, List
import ast

GHIDRA_DIR = Path(".ghidra_analyzer")
ANALYSIS_LOG = GHIDRA_DIR / "analyses.jsonl"

SAFE_ROOT = Path(os.environ.get("GHIDRA_ANALYZER_ROOT", ".")).resolve()
ALLOWED_FILE_TYPES = {"*", ".py", ".js", ".ts", ".jsx", ".tsx", ".txt", ".md", ".json", ".yaml", ".yml"}


def _safe_path(user_path: str, *, must_be_file: bool = False, must_be_dir: bool = False) -> Path:
    if not isinstance(user_path, str) or not user_path.strip():
        raise ValueError("Invalid path")

    raw = Path(user_path)

    # Reject absolute paths. Only allow paths relative to SAFE_ROOT.
    if raw.is_absolute():
        raise ValueError("Absolute paths are not allowed")

    # Reject traversal components before any filesystem access.
    if any(part == ".." for part in raw.parts):
        raise ValueError("Path traversal is not allowed")

    resolved = (SAFE_ROOT / raw).resolve()

    # Prevent symlink escape: ensure resolved path is still within SAFE_ROOT.
    try:
        resolved.relative_to(SAFE_ROOT)
    except ValueError:
        raise ValueError("Path is outside the allowed workspace")

    if must_be_file and not resolved.is_file():
        raise FileNotFoundError("Requested file was not found")

    if must_be_dir and not resolved.is_dir():
        raise FileNotFoundError("Requested directory was not found")

    return resolved


def _safe_file_type(file_type: Optional[str]) -> str:
    if file_type is None:
        return "*"

    if file_type not in ALLOWED_FILE_TYPES:
        raise ValueError("Unsupported file type")

    return file_type


def _literal_pattern(pattern: str) -> str:
    if not isinstance(pattern, str) or len(pattern) > 200:
        raise ValueError("Invalid search pattern")

    # Treat user input as literal text, not regex.
    return re.escape(pattern)


@dataclass
class CodeAnalysis:
    """Deep analysis of code structure and patterns."""
    analysis_id: str
    target_file: str
    analysis_type: str
    findings: Dict
    complexity_score: float
    risk_flags: List[str]
    patterns_found: List[str]
    recommendations: List[str]
    analyzed_at: str


class GhidraAnalyzerSkill:
    """
    Reverse engineer and deeply analyze code structure.
    Like Ghidra: understand what the code is ACTUALLY doing,
    not just what it says it does.
    """

    def __init__(self):
        GHIDRA_DIR.mkdir(parents=True, exist_ok=True)

    def analyze_file(self, file_path: str, deep: bool = False) -> Dict:
        """
        Analyze a code file: structure, patterns, complexity, risks.
        
        Args:
            file_path: Python, JS, or any text file (relative to SAFE_ROOT)
            deep: if True, do recursive dependency analysis
        
        Returns: comprehensive analysis of what the code does
        """
        try:
            path = _safe_path(file_path, must_be_file=True)
        except FileNotFoundError:
            return {"error": "File not found"}
        except ValueError:
            return {"error": "Invalid file path"}

        analysis_id = hashlib.sha256(f"{path}:{datetime.now().isoformat()}".encode()).hexdigest()[:12]

        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return {"error": "Cannot read file"}

        file_ext = path.suffix.lower()

        if file_ext == ".py":
            analysis = self._analyze_python(content, str(path.relative_to(SAFE_ROOT)), analysis_id)
        elif file_ext in [".js", ".ts", ".jsx", ".tsx"]:
            analysis = self._analyze_javascript(content, str(path.relative_to(SAFE_ROOT)), analysis_id)
        else:
            analysis = self._analyze_generic(content, str(path.relative_to(SAFE_ROOT)), analysis_id)

        return analysis

    def _analyze_python(self, content: str, file_path: str, analysis_id: str) -> Dict:
        """Deep analysis of Python code."""
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return {"error": "Syntax error in Python file"}

        findings = {
            "functions": [],
            "classes": [],
            "imports": [],
            "global_vars": [],
            "async_funcs": [],
            "exception_handlers": [],
        }

        risk_flags = []
        patterns = []

        # Extract structure
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                findings["functions"].append({
                    "name": node.name,
                    "args": [arg.arg for arg in node.args.args],
                    "lines": node.end_lineno - node.lineno if node.lineno else 0,
                })
            elif isinstance(node, ast.AsyncFunctionDef):
                findings["async_funcs"].append(node.name)
            elif isinstance(node, ast.ClassDef):
                methods = [n.name for n in node.body if isinstance(n, ast.FunctionDef)]
                findings["classes"].append({"name": node.name, "methods": methods})
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    findings["imports"].append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                findings["imports"].append(f"from {node.module}")
            elif isinstance(node, ast.Try):
                risk_flags.append("exception_handling_present")
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    if node.func.id in ["eval", "exec", "__import__"]:
                        risk_flags.append(f"dangerous_function: {node.func.id}")

        # Pattern detection
        if findings["async_funcs"]:
            patterns.append("async_processing")
        if any("db" in imp.lower() or "sql" in imp.lower() for imp in findings["imports"]):
            patterns.append("database_interaction")
        if any("http" in imp.lower() or "requests" in imp.lower() for imp in findings["imports"]):
            patterns.append("network_calls")
        if any("crypt" in imp.lower() or "hash" in imp.lower() for imp in findings["imports"]):
            patterns.append("security_crypto")

        complexity = self._estimate_complexity(findings)

        analysis = CodeAnalysis(
            analysis_id=analysis_id,
            target_file=file_path,
            analysis_type="python_structure",
            findings=findings,
            complexity_score=complexity,
            risk_flags=list(set(risk_flags)),
            patterns_found=patterns,
            recommendations=self._recommend_for_python(findings, patterns, risk_flags),
            analyzed_at=datetime.now(timezone.utc).isoformat(),
        )

        self._log_analysis(asdict(analysis))
        return asdict(analysis)

    def _analyze_javascript(self, content: str, file_path: str, analysis_id: str) -> Dict:
        """Deep analysis of JavaScript/TypeScript code."""
        findings = {
            "functions": [],
            "classes": [],
            "imports": [],
            "exports": [],
            "async_funcs": [],
            "api_calls": [],
            "state_mutations": [],
        }

        risk_flags = []
        patterns = []

        # Regex-based analysis (since JS AST parsing is complex)
        function_pattern = r"(async\s+)?function\s+(\w+)|const\s+(\w+)\s*=\s*(async\s*)?\("
        class_pattern = r"class\s+(\w+)"
        import_pattern = r"(?:import|require)\s+(?:.*?from\s+)?['\"]([^'\"]+)"
        export_pattern = r"export\s+(?:async\s+)?(?:function|const|class)\s+(\w+)"

        for match in re.finditer(function_pattern, content):
            func_name = match.group(2) or match.group(3)
            is_async = "async" in match.group(0)
            if func_name:
                findings["functions"].append({"name": func_name, "async": is_async})
                if is_async:
                    findings["async_funcs"].append(func_name)

        for match in re.finditer(class_pattern, content):
            findings["classes"].append(match.group(1))

        for match in re.finditer(import_pattern, content):
            findings["imports"].append(match.group(1))

        for match in re.finditer(export_pattern, content):
            findings["exports"].append(match.group(1))

        # Detect API calls
        api_pattern = r"(?:fetch|axios|http\.(?:get|post|put|delete))\s*\("
        findings["api_calls"] = [m.group(0) for m in re.finditer(api_pattern, content)]

        # Detect state mutations
        if "useState" in content:
            patterns.append("react_hooks")
        if "Redux" in content or "useSelector" in content:
            patterns.append("redux_state")
        if "const.*=" in content and "async" in content:
            patterns.append("async_state_management")

        # Risk detection
        if "eval(" in content or "Function(" in content:
            risk_flags.append("dynamic_code_execution")
        if "localStorage" in content or "sessionStorage" in content:
            patterns.append("client_storage")
        if findings["api_calls"]:
            patterns.append("api_integration")

        complexity = self._estimate_complexity(findings)

        analysis = CodeAnalysis(
            analysis_id=analysis_id,
            target_file=file_path,
            analysis_type="javascript_structure",
            findings=findings,
            complexity_score=complexity,
            risk_flags=list(set(risk_flags)),
            patterns_found=patterns,
            recommendations=self._recommend_for_javascript(findings, patterns, risk_flags),
            analyzed_at=datetime.now(timezone.utc).isoformat(),
        )

        self._log_analysis(asdict(analysis))
        return asdict(analysis)

    def _analyze_generic(self, content: str, file_path: str, analysis_id: str) -> Dict:
        """Generic analysis for any text file."""
        lines = content.split("\n")
        findings = {
            "total_lines": len(lines),
            "code_lines": len([l for l in lines if l.strip() and not l.strip().startswith("#")]),
            "blank_lines": len([l for l in lines if not l.strip()]),
            "comment_lines": len([l for l in lines if l.strip().startswith("#")]),
            "keywords_found": self._extract_keywords(content),
        }

        risk_flags = []
        patterns = []

        if "TODO" in content or "FIXME" in content:
            patterns.append("has_todo_comments")
        if "HACK" in content:
            risk_flags.append("has_hack_workaround")

        complexity = min(len(lines) / 100, 1.0)  # Rough estimate

        analysis = CodeAnalysis(
            analysis_id=analysis_id,
            target_file=file_path,
            analysis_type="generic_text",
            findings=findings,
            complexity_score=complexity,
            risk_flags=risk_flags,
            patterns_found=patterns,
            recommendations=[],
            analyzed_at=datetime.now(timezone.utc).isoformat(),
        )

        self._log_analysis(asdict(analysis))
        return asdict(analysis)

    def architecture_map(self, directory: str = ".", recursive: bool = True) -> Dict:
        """
        Map the architecture of a directory: files, structure, dependencies.
        Like Ghidra's call graph but for filesystem.
        """
        try:
            dir_path = _safe_path(directory, must_be_dir=True)
        except FileNotFoundError:
            return {"error": "Directory not found"}
        except ValueError:
            return {"error": "Invalid directory"}

        file_types = {}

        pattern = "**/*" if recursive else "*"

        for item in dir_path.glob(pattern):
            if item.name.startswith("."):
                continue

            try:
                # Guard against symlinked entries escaping SAFE_ROOT.
                item.resolve().relative_to(SAFE_ROOT)
            except ValueError:
                continue

            file_type = "file" if item.is_file() else "directory"

            if file_type == "file":
                ext = item.suffix or "no_extension"
                file_types[ext] = file_types.get(ext, 0) + 1

        return {
            "root": str(dir_path.relative_to(SAFE_ROOT)),
            "file_type_distribution": file_types,
            "total_files": sum(file_types.values()),
            "architecture_note": f"Directory contains {sum(file_types.values())} files of {len(file_types)} types",
        }

    def find_patterns(self, pattern: str, directory: str = ".", file_type: str = "*") -> Dict:
        """Find literal code patterns across files."""
        try:
            dir_path = _safe_path(directory, must_be_dir=True)
            safe_file_type = _safe_file_type(file_type)
            safe_pattern = _literal_pattern(pattern)
        except ValueError:
            return {"error": "Invalid scan parameters"}

        matches = []

        glob_pattern = "**/*" if safe_file_type == "*" else f"**/*{safe_file_type}"

        for file_path in dir_path.glob(glob_pattern):
            if file_path.name.startswith("."):
                continue

            try:
                # Guard against symlinked entries escaping SAFE_ROOT.
                file_path.resolve().relative_to(SAFE_ROOT)
            except ValueError:
                continue

            if not file_path.is_file():
                continue

            try:
                content = file_path.read_text(encoding="utf-8", errors="replace")
                if re.search(safe_pattern, content):
                    matches.append({
                        "file": str(file_path.relative_to(SAFE_ROOT)),
                        "matches": len(re.findall(safe_pattern, content)),
                    })
            except Exception:
                pass

        return {
            "pattern": pattern,
            "files_with_matches": len(matches),
            "matches": matches,
        }

    def _estimate_complexity(self, findings: Dict) -> float:
        """Estimate cyclomatic complexity from findings."""
        score = 0.0
        score += len(findings.get("functions", [])) * 0.1
        score += len(findings.get("classes", [])) * 0.15
        score += len(findings.get("imports", [])) * 0.05
        return min(score, 1.0)

    def _extract_keywords(self, content: str) -> List[str]:
        """Extract programming keywords from content."""
        keywords = {
            "class", "function", "def", "return", "async", "await",
            "import", "export", "const", "let", "var", "if", "for", "while",
        }
        found = []
        for kw in keywords:
            if kw in content.lower():
                found.append(kw)
        return found

    def _recommend_for_python(self, findings: Dict, patterns: List[str], risks: List[str]) -> List[str]:
        """Recommendations for Python code."""
        recs = []
        if len(findings.get("functions", [])) > 20:
            recs.append("Consider breaking into modules; too many functions in one file")
        if "exception_handling_present" in risks:
            recs.append("Good: exception handling detected")
        if any("dangerous" in r for r in risks):
            recs.append("WARNING: dangerous functions detected; review security")
        return recs

    def _recommend_for_javascript(self, findings: Dict, patterns: List[str], risks: List[str]) -> List[str]:
        """Recommendations for JavaScript code."""
        recs = []
        if "react_hooks" in patterns:
            recs.append("React hooks detected; ensure proper dependency arrays")
        if findings.get("api_calls"):
            recs.append(f"Found {len(findings['api_calls'])} API calls; ensure error handling")
        if "dynamic_code_execution" in risks:
            recs.append("RISK: dynamic code execution detected; review security")
        return recs

    def _log_analysis(self, analysis: Dict):
        """Log analysis results."""
        with open(ANALYSIS_LOG, "a") as f:
            f.write(json.dumps(analysis) + "\n")

    def get_analyses(self, limit: int = 20) -> List[Dict]:
        """Get recent analyses."""
        if not ANALYSIS_LOG.exists():
            return []
        lines = [l for l in ANALYSIS_LOG.read_text().split("\n") if l.strip()]
        return [json.loads(l) for l in lines[-limit:]]

    def get_stats(self) -> Dict:
        """Get analysis statistics."""
        analyses = self.get_analyses(100)
        return {
            "total_analyses": len(analyses),
            "files_analyzed": len(set(a.get("target_file") for a in analyses)),
            "avg_complexity": round(sum(a.get("complexity_score", 0) for a in analyses) / max(len(analyses), 1), 2),
        }


_ghidra: Optional[GhidraAnalyzerSkill] = None

def get_ghidra() -> GhidraAnalyzerSkill:
    global _ghidra
    if _ghidra is None:
        _ghidra = GhidraAnalyzerSkill()
    return _ghidra
