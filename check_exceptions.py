#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check_exceptions.py -- StageError Contract Enforcement
=====================================================
بيدور على كل "except Exception" في الملفات الجوهرية
ويتأكد انها بترفع StageError مش بتبلعها صامت.

الاستخدام:
    python check_exceptions.py              # يفحص CORE_FILES
    python check_exceptions.py --all        # يفحص كل الـ .py files

Exit codes:
    0 = كل حاجة تمام
    1 = في violations

مناسب يتضاف كـ pre-commit hook:
    # .git/hooks/pre-commit
    python check_exceptions.py || exit 1
"""

import ast
import os
import sys
from pathlib import Path
from typing import Optional

# ============================================================
# الملفات الجوهرية
# ============================================================

CORE_FILES = [
    "executive_brain.py",
    "adam_runtime.py",
    "adam_mind.py",
]

# ============================================================
# Allowlists -- (filename, class, function)
#
# BOUNDARY_FUNCTIONS:
#   Runtime boundary -- بيمسك exception ويحوّله لـ user-facing string
#   مسموح بـ logger.error + return string بدون raise
#
# NON_CRITICAL_FUNCTIONS:
#   Non-critical stages -- فشلهم مش المفروض يوقف الـ pipeline
#   مسموح بـ logger.warning بدون raise
#
# ملاحظة: run_scheduled مش في الـ allowlist لأنه بيعمل raise --
#   لو حد غيّره لـ return None مستقبلاً، الـchecker هيمسكه فوراً.
# ============================================================

BOUNDARY_FUNCTIONS = {
    ("adam_runtime.py", "AdamRuntime", "run"),
}

NON_CRITICAL_FUNCTIONS = {
    ("executive_brain.py", "ExecutiveBrain", "_stage_learn"),
    ("adam_mind.py",       "AdamMind",       "_deep_analyze"),
}


# ============================================================
# ExceptionChecker -- AST Visitor
# ============================================================

class ExceptionChecker(ast.NodeVisitor):
    """
    بيتتبع:
        self._current_class    -- اسم الـ class الحالي
        self._current_function -- اسم الدالة الحالية

    بيقارن (filename, class, function) مش اسم الدالة بس.
    """

    def __init__(self, filename: str):
        self.filename         = os.path.basename(filename)
        self.violations       = []
        self._current_class   = None
        self._current_function= None

    # ----------------------------------------------------------------
    # Class tracking
    # ----------------------------------------------------------------

    def visit_ClassDef(self, node: ast.ClassDef):
        old = self._current_class
        self._current_class = node.name
        self.generic_visit(node)
        self._current_class = old

    # ----------------------------------------------------------------
    # Function tracking
    # ----------------------------------------------------------------

    def visit_FunctionDef(self, node: ast.FunctionDef):
        old = self._current_function
        self._current_function = node.name
        self.generic_visit(node)
        self._current_function = old

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        old = self._current_function
        self._current_function = node.name
        self.generic_visit(node)
        self._current_function = old

    # ----------------------------------------------------------------
    # Exception handling check
    # ----------------------------------------------------------------

    def visit_ExceptHandler(self, node: ast.ExceptHandler):
        if not self._is_broad_catch(node):
            self.generic_visit(node)
            return

        violation = self._check_body(node)
        if violation:
            self.violations.append({
                "file":     self.filename,
                "class":    self._current_class or "(module)",
                "function": self._current_function or "(module)",
                "line":     node.lineno,
                "issue":    violation,
            })

        self.generic_visit(node)

    # ----------------------------------------------------------------
    # Helpers
    # ----------------------------------------------------------------

    def _is_broad_catch(self, node: ast.ExceptHandler) -> bool:
        """
        هل الـ handler بيمسك Exception العامة؟
        بيشمل:
          except Exception:
          except (Exception, ValueError):  <- tuple catch
          bare except:
        """
        if node.type is None:
            return True
        if isinstance(node.type, ast.Name):
            return node.type.id in ("Exception", "BaseException")
        # tuple: except (Exception, SomethingElse)
        if isinstance(node.type, ast.Tuple):
            return any(
                isinstance(elt, ast.Name) and elt.id in ("Exception", "BaseException")
                for elt in node.type.elts
            )
        return False

    def _location(self) -> tuple:
        return (
            self.filename,
            self._current_class   or "",
            self._current_function or "",
        )

    def _check_body(self, node: ast.ExceptHandler) -> Optional[str]:
        """
        بيرجع وصف المشكلة لو في violation.
        None لو مقبول.
        """
        loc = self._location()
        fn  = self._current_function or "?"
        cls = self._current_class    or "?"

        # ----------------------------------------------------------------
        # BOUNDARY: لازم logger.error(...) + return <non-None-literal>
        #
        # ملاحظة صريحة عن حدود الفحص:
        #   _has_string_return بتثبت "مش None/int/bool literal"
        #   مش بتثبت "string مضمون" -- static type inference خارج نطاق checker.
        #   مثلاً: return value / return func() بيعدوا حتى لو الناتج مش str.
        #
        # TODO v2: replace raw string return with typed ErrorResponse:
        #   @dataclass
        #   class ErrorResponse:
        #       message: str
        #       stage:   str
        #   والـ Runtime يحوّله لـ text -- عقد أقوى وقابل للفحص الكامل.
        # ----------------------------------------------------------------
        if loc in BOUNDARY_FUNCTIONS:
            has_error      = self._has_logger_call(node, "error")
            has_str_return = self._has_string_return(node)
            if has_error and has_str_return:
                return None
            missing = []
            if not has_error:
                missing.append("logger.error(...)")
            if not has_str_return:
                missing.append("return <non-None value>")
            return "Boundary [" + cls + "." + fn + "] محتاج: " + " + ".join(missing)

        # ----------------------------------------------------------------
        # NON-CRITICAL: لازم logger.warning(...) فعلي في نفس الـ scope
        # (مش في nested function)
        # ----------------------------------------------------------------
        if loc in NON_CRITICAL_FUNCTIONS:
            if self._has_logger_call(node, "warning"):
                return None
            return "Non-critical [" + cls + "." + fn + "] محتاج logger.warning(...) في الـ handler مباشرة"

        # ----------------------------------------------------------------
        # كل دالة تانية: لازم raise StageError مباشرة (unconditional)
        #
        # قاعدتان معاً:
        #   1. StageError بالاسم -- مش اي raise (raise ValueError مش كافي)
        #   2. Direct statement -- مش داخل if/try/with (conditional raise مش كافي)
        #
        # مقبول:
        #   raise StageError(stage="x", original_error=e)  <- explicit
        #   raise                                           <- bare re-raise
        #
        # مرفوض:
        #   raise ValueError()     <- مش StageError
        #   raise RuntimeError()   <- مش StageError
        #   if cond: raise StageError(...)  <- conditional = ممكن يتجاوز
        # ----------------------------------------------------------------
        stage_error_ok, raise_wrong_type, raise_conditional = \
            self._check_raise_quality(node)

        if stage_error_ok:
            return None

        if raise_conditional:
            return (
                "except Exception في [" + cls + "." + fn + "]: "
                + "raise StageError موجود لكن داخل if/try -- "
                + "لازم يكون direct statement بدون شرط"
            )

        if raise_wrong_type:
            return (
                "except Exception في [" + cls + "." + fn + "]: "
                + "raise موجود لكن مش StageError -- "
                + "يلزم raise StageError(stage=..., original_error=e)"
            )

        has_logger = self._has_logger_call(node, None)
        note = " -- هل المفروض تكون في NON_CRITICAL_FUNCTIONS?" if has_logger else ""
        return (
            "except Exception في [" + cls + "." + fn + "] "
            + "بدون raise StageError" + note
        )

    # ----------------------------------------------------------------
    # _walk_no_nested -- ast.walk بيوقف عند FunctionDef
    # ----------------------------------------------------------------

    def _walk_stmt(self, node: ast.AST):
        """
        Walk AST stopping at nested function boundaries.
        Stops BEFORE entering FunctionDef -- does not yield it either.

        Unlike the previous _walk_no_nested which yielded the node first
        then checked children, this stops completely at any FunctionDef,
        so logger.warning() or raise inside def inner() is invisible.
        """
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return
        yield node
        for child in ast.iter_child_nodes(node):
            yield from self._walk_stmt(child)

    def _check_raise_quality(self, node: ast.ExceptHandler) -> tuple:
        """
        يفحص جودة الـ raise في الـ handler.
        بيرجع tuple: (stage_error_ok, raise_wrong_type, raise_conditional)

        stage_error_ok:    في raise StageError أو bare raise مباشرة
        raise_wrong_type:  في raise لكن مش StageError (e.g. ValueError)
        raise_conditional: في raise StageError لكن داخل if/try (مش direct)

        الأولوية: stage_error_ok > raise_conditional > raise_wrong_type
        """
        # فحص الـ direct statements -- أول raise هو الذي يحسم
        # أي raise بعده unreachable فلا يُحسب
        for stmt in node.body:
            if not isinstance(stmt, ast.Raise):
                continue

            # bare raise = re-raise مقبول
            if stmt.exc is None:
                return (True, False, False)

            exc = stmt.exc
            # raise StageError(...)
            if isinstance(exc, ast.Call):
                if isinstance(exc.func, ast.Name) and exc.func.id == "StageError":
                    return (True, False, False)
            # raise StageError (بدون args)
            if isinstance(exc, ast.Name) and exc.id == "StageError":
                return (True, False, False)

            # أول direct raise موجود لكن مش StageError -> violation فورية
            # أي StageError بعده unreachable ولا يُعتد بيه
            return (False, True, False)

        # مفيش direct StageError raise -- نشوف لو في raise داخل if/try
        has_conditional_stage_error = False
        has_wrong_type_raise        = False

        for stmt in node.body:
            for item in self._walk_stmt(stmt):
                if not isinstance(item, ast.Raise):
                    continue
                if item.exc is None:
                    has_conditional_stage_error = True
                    continue
                exc = item.exc
                is_stage = (
                    (isinstance(exc, ast.Call) and
                     isinstance(exc.func, ast.Name) and
                     exc.func.id == "StageError") or
                    (isinstance(exc, ast.Name) and exc.id == "StageError")
                )
                if is_stage:
                    has_conditional_stage_error = True
                else:
                    has_wrong_type_raise = True

        return (False, has_wrong_type_raise, has_conditional_stage_error)

    def _has_logger_call(self, node: ast.ExceptHandler, method) -> bool:
        for stmt in node.body:
            for item in self._walk_stmt(stmt):
                if not isinstance(item, ast.Call):
                    continue
                func = item.func
                if not isinstance(func, ast.Attribute):
                    continue
                if not isinstance(func.value, ast.Name):
                    continue
                if func.value.id != "logger":
                    continue
                if method is None or func.attr == method:
                    return True
        return False

    def _has_string_return(self, node: ast.ExceptHandler) -> bool:
        """
        Checks for return with non-None/int/bool value.
        Known limitation: cannot verify that variable/call returns str.
        TODO v2: replace with typed ErrorResponse to enable static check.
        """
        for stmt in node.body:
            if not isinstance(stmt, ast.Return):
                continue
            val = stmt.value
            if val is None:
                continue
            if isinstance(val, ast.Constant):
                if isinstance(val.value, str) and val.value:
                    return True
                continue
            if isinstance(val, (ast.JoinedStr, ast.Name, ast.Call, ast.BinOp, ast.IfExp)):
                return True
        return False


# ============================================================
# check_file
# ============================================================

def check_file(filepath: str) -> list:
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            source = f.read()
        tree    = ast.parse(source, filename=filepath)
        checker = ExceptionChecker(filepath)
        checker.visit(tree)
        return checker.violations
    except SyntaxError as e:
        return [{"file": filepath, "class": "?", "function": "?",
                 "line": e.lineno, "issue": "Syntax error: " + str(e)}]
    except Exception as e:
        return [{"file": filepath, "class": "?", "function": "?",
                 "line": 0, "issue": "فشل الفحص: " + str(e)}]


# ============================================================
# main
# ============================================================

def main():
    check_all = "--all" in sys.argv

    if check_all:
        all_py = list(Path(".").rglob("*.py"))
        files  = [str(f) for f in all_py if "__pycache__" not in str(f)]
    else:
        files = [f for f in CORE_FILES if os.path.exists(f)]

    if not files:
        print("مفيش ملفات للفحص.")
        return 0

    all_violations = []
    for fp in files:
        all_violations.extend(check_file(fp))

    print("=" * 50)
    print("StageError Contract Check")
    print("=" * 50)
    print("فحصت: " + str(len(files)) + " ملف")

    if not all_violations:
        print("كل حاجة تمام -- مفيش violations")
        return 0

    print("Violations: " + str(len(all_violations)))
    print("-" * 50)
    for v in all_violations:
        print("FILE:     " + v["file"])
        print("CLASS:    " + v.get("class", "?"))
        print("FUNCTION: " + v.get("function", "?"))
        print("LINE:     " + str(v["line"]))
        print("ISSUE:    " + v["issue"])
        print()

    return 1


if __name__ == "__main__":
    sys.exit(main())
