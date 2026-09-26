"""Module ownership and dependency direction from ADR 0016 (#118)."""
import ast
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'bridge'
LOCAL = {path.stem for path in SOURCE.glob('*.py')}

# Deliberate function-level imports of local modules, each with its reason. Anything else is a
# cycle-breaking import that the dependency direction should make unnecessary.
LAZY = {
    # The CLI loads a command family only when it runs, so hooks and status never import HTTP
    # listeners, enrollment prompts or the controller's optional contract dependencies.
    ('bridge', 'controller_server'): 'command family',
    ('bridge', 'enrollment'): 'command family',
    ('bridge', 'wall_server'): 'command family',
    # Optional listener dependency: requirements-controller.txt.
    ('controller_server', 'controller_contract'): 'optional dependency',
}


def imports(path):
    """Local modules imported at module level and inside functions."""
    tree = ast.parse(path.read_text(encoding='utf-8'))
    top, lazy = set(), set()
    def names(node):
        if isinstance(node, ast.Import):
            return {alias.name.split('.')[0] for alias in node.names}
        if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            return {node.module.split('.')[0]}
        return set()
    for node in tree.body:
        top |= names(node) & LOCAL
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for inner in ast.walk(node):
                lazy |= names(inner) & LOCAL
    return top, lazy - top, tree


class ModuleDependencyTest(unittest.TestCase):
    def setUp(self):
        self.graph = {path.stem: imports(path) for path in SOURCE.glob('*.py')}

    def test_no_module_receives_or_imports_the_bridge_entry_point(self):
        for module, (top, lazy, tree) in self.graph.items():
            with self.subTest(module=module):
                self.assertNotIn('bridge', top | lazy)
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        arguments = [a.arg for a in node.args.posonlyargs + node.args.args + node.args.kwonlyargs]
                        self.assertFalse({'b', 'bridge'} & set(arguments), f'{module}.{node.name} takes the bridge module')
                    if isinstance(node, ast.Call) and getattr(node.func, 'id', None) == 'globals':
                        self.fail(f'{module} hands its globals to another module')

    def test_module_level_imports_follow_one_direction(self):
        order, visiting = [], set()
        def visit(module, path=()):
            if module in order: return
            self.assertNotIn(module, visiting, 'import cycle: ' + ' -> '.join(path + (module,)))
            visiting.add(module)
            for dependency in sorted(self.graph[module][0]):
                visit(dependency, path + (module,))
            visiting.discard(module); order.append(module)
        for module in sorted(self.graph):
            visit(module)

    def test_function_level_imports_are_documented_exceptions(self):
        found = {(module, dependency) for module, (_, lazy, _) in self.graph.items() for dependency in lazy}
        self.assertEqual(found, set(LAZY))
        # A lazy import may not hide a cycle either: the importer never sits below its target.
        for module, dependency in LAZY:
            self.assertNotIn(module, self.closure(dependency))

    def closure(self, module):
        seen, stack = set(), [module]
        while stack:
            for dependency in self.graph[stack.pop()][0]:
                if dependency not in seen:
                    seen.add(dependency); stack.append(dependency)
        return seen

    def test_integration_configuration_path_never_reaches_the_browser_adapter(self):
        for module in ('integration_api', 'edits'):
            with self.subTest(module=module):
                self.assertNotIn('wall_server', self.closure(module) | {module})
                constants = [node.value for node in ast.walk(self.graph[module][2])
                             if isinstance(node, ast.Constant) and isinstance(node.value, str)]
                self.assertFalse([value for value in constants if value.startswith('/api/')])
        # The worker's configuration step reaches the same edits without the browser adapter.
        self.assertIn('edits', self.closure('integration_api'))
        self.assertIn('edits', self.closure('wall_server'))

    def test_demo_and_tests_inject_device_and_launch_seams(self):
        demo = ast.parse((ROOT / 'scripts/demo.py').read_text(encoding='utf-8'))
        modules = {alias.asname or alias.name for node in ast.walk(demo) if isinstance(node, ast.Import) for alias in node.names}
        rebound = [ast.unparse(target) for node in ast.walk(demo) if isinstance(node, ast.Assign) for target in node.targets
                   if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name) and target.value.id in modules]
        self.assertEqual(rebound, [], 'the demo must not rebind module attributes')
        pattern = re.compile(r"patch\.object\(b, '(light_request|launch_worker)'|\bb\.(light_request|launch_worker|subprocess\.Popen)\s*=")
        for path in sorted((ROOT / 'tests').glob('*.py')):
            with self.subTest(test=path.name):
                self.assertIsNone(pattern.search(path.read_text(encoding='utf-8')))


if __name__ == '__main__':
    unittest.main()
