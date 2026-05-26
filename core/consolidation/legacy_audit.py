import ast
import os
import json
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import List, Dict, Any

@dataclass
class LegacyAccessReport:
    file_path: str
    line_number: int
    access_type: str
    risk_level: str  # HIGH, MEDIUM, LOW
    suggested_fix: str

class LegacyAccessVisitor(ast.NodeVisitor):
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.reports: List[LegacyAccessReport] = []
        
        # 风险特征
        self.legacy_files = {"config.json", "cookies.txt", "pipeline_cache.json"}
        self.legacy_extensions = {".json", ".txt"}

    def add_report(self, node: ast.AST, access_type: str, risk_level: str, suggested_fix: str):
        self.reports.append(LegacyAccessReport(
            file_path=self.file_path,
            line_number=getattr(node, 'lineno', -1),
            access_type=access_type,
            risk_level=risk_level,
            suggested_fix=suggested_fix
        ))

    def visit_Call(self, node: ast.Call):
        # 检查是否调用了 open()
        if isinstance(node.func, ast.Name) and node.func.id == 'open':
            if node.args and isinstance(node.args[0], ast.Constant):
                file_arg = str(node.args[0].value)
                if any(lf in file_arg for lf in self.legacy_files):
                    self.add_report(node, f"Legacy file open: {file_arg}", "HIGH", "Migrate to StorageGateway / AppContext")
                elif any(file_arg.endswith(ext) for ext in self.legacy_extensions):
                    self.add_report(node, f"Possible legacy file open: {file_arg}", "MEDIUM", "Ensure safe_open or unified storage is used")
            self.add_report(node, "Raw open() call", "LOW", "Use core.consolidation.write_guard.safe_open or core.paths")

        # 检查 json.load / json.dump
        elif isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name) and node.func.value.id == 'json':
                if node.func.attr in ('load', 'dump'):
                    self.add_report(node, f"Direct json.{node.func.attr} call", "MEDIUM", "Migrate to StorageGateway or check write_guard")
            # 检查 sqlite3.connect
            elif isinstance(node.func.value, ast.Name) and node.func.value.id == 'sqlite3':
                if node.func.attr == 'connect':
                    self.add_report(node, "Manual sqlite3.connect()", "HIGH", "Use core.database.DBManager via AppContext")

        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant):
        # 检查是否直接使用了旧文件的字符串字面量
        if isinstance(node.value, str):
            if any(lf in node.value for lf in self.legacy_files):
                self.add_report(node, f"Legacy file path literal: {node.value}", "HIGH", "Use core.paths and StorageGateway")
        self.generic_visit(node)


class LegacyAuditor:
    def __init__(self, root_dir: str):
        self.root_dir = Path(root_dir)

    def scan_file(self, file_path: Path) -> List[LegacyAccessReport]:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                source = f.read()
            tree = ast.parse(source, filename=str(file_path))
            visitor = LegacyAccessVisitor(str(file_path))
            visitor.visit(tree)
            return visitor.reports
        except Exception as e:
            # 忽略无法解析或非法的 python 文件
            return []

    def run_audit(self) -> List[LegacyAccessReport]:
        all_reports = []
        for py_file in self.root_dir.rglob("*.py"):
            # 排除当前迁移模块本身
            if "consolidation" in py_file.parts or "migrations" in py_file.parts:
                continue
            
            reports = self.scan_file(py_file)
            all_reports.extend(reports)
        
        return all_reports

    def print_report(self, reports: List[LegacyAccessReport]):
        print(f"\n{'='*60}")
        print(f"Legacy Access Audit Report (Total Issues: {len(reports)})")
        print(f"{'='*60}")
        
        # 按风险级别分类
        high = [r for r in reports if r.risk_level == "HIGH"]
        medium = [r for r in reports if r.risk_level == "MEDIUM"]
        low = [r for r in reports if r.risk_level == "LOW"]
        
        def print_category(category_name, items):
            if not items: return
            print(f"\n[{category_name}] ({len(items)} issues)")
            for r in items:
                print(f"  {r.file_path}:{r.line_number}")
                print(f"    - Type: {r.access_type}")
                print(f"    - Fix:  {r.suggested_fix}")
                
        print_category("HIGH RISK (Must Fix)", high)
        print_category("MEDIUM RISK", medium)
        print_category("LOW RISK", low)
        print(f"\n{'='*60}")


if __name__ == "__main__":
    # 可以直接运行来扫描整个项目
    # 假设脚本在 d:/red/redtoolbox/core/consolidation/legacy_audit.py
    project_root = Path(__file__).parent.parent.parent
    auditor = LegacyAuditor(str(project_root))
    reports = auditor.run_audit()
    auditor.print_report(reports)
