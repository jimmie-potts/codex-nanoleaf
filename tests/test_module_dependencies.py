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



UNAUDITED = (('_posixsubprocess', 'fork_exec', 'process'), ('_interpreters', 'create', 'subinterpreter'),
             ('_xxsubinterpreters', 'create', 'subinterpreter'))


SETTERS = {'setattr', 'delattr', '__setattr__', '__delattr__'}
MODULE_CALLS = {'importlib.import_module', 'import_module', '__import__'}


def rebinding_problems(source):
    """Ways the demo source replaces something on another module; an empty list means none.

    The single allowed replacement is the process boundary's: one setattr, inside install_boundary,
    in a for loop over exactly UNAUDITED, on the module that loop imports by the loop's own name.
    An assigned or deleted attribute is resolved through its attribute and subscript chain to a
    root: an imported name, a local name assigned from one, importlib.import_module(...) or
    sys.modules[...]. setattr and delattr may only be called by name, never bound, imported,
    reached as an attribute or named in a string. A static check cannot be complete: deliberately
    obfuscated rebinding, such as through exec, stays out of scope (#196).
    """
    tree = ast.parse(source)
    parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules |= {alias.asname or alias.name.split('.')[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            modules |= {alias.asname or alias.name for alias in node.names}

    def rooted(node):
        """True when node is reached from another module's namespace."""
        while isinstance(node, (ast.Attribute, ast.Subscript)):
            node = node.value
        if isinstance(node, ast.Call):
            return ast.unparse(node.func) in MODULE_CALLS
        return isinstance(node, ast.Name) and node.id in modules

    # A local alias of a module or of something on one, such as `module = wall_server` or `app = wall_server.App`.
    bindings = [(target.id, node.value) for node in ast.walk(tree)
                for target in (node.targets if isinstance(node, ast.Assign) else [node.target]
                               if isinstance(node, (ast.AnnAssign, ast.NamedExpr)) and node.value else [])
                if isinstance(target, ast.Name)]
    while aliases := {name for name, value in bindings if name not in modules and rooted(value)}:
        modules |= aliases
    problems = []
    for node in ast.walk(tree):
        text = ast.unparse(node)
        written = isinstance(getattr(node, 'ctx', None), (ast.Store, ast.Del))
        if written and isinstance(node, ast.Attribute) and rooted(node):
            problems.append(f'module attribute assignment: {text}')
        if written and isinstance(node, ast.Subscript) and (
                (isinstance(node.value, ast.Attribute) and node.value.attr == '__dict__')
                or (isinstance(node.value, ast.Call) and ast.unparse(node.value.func) in ('vars', 'globals'))
                or ast.unparse(node.value) == 'sys.modules'):
            problems.append(f'namespace assignment: {text}')
        if isinstance(node, ast.Call) and ast.unparse(node.func) == 'delattr':
            problems.append(f'attribute replacement: {text}')
        if isinstance(node, ast.Attribute) and node.attr in SETTERS:
            problems.append(f'attribute replacement: {text}')
        if isinstance(node, ast.Name) and node.id in SETTERS and not (isinstance(parents.get(node), ast.Call) and parents[node].func is node):
            problems.append(f'{node.id} used other than by a call: {ast.unparse(parents[node])}')
        if isinstance(node, ast.ImportFrom) and {alias.name for alias in node.names} & SETTERS:
            problems.append(f'setattr imported: {text}')
        if isinstance(node, ast.Constant) and node.value in SETTERS:
            problems.append(f'setattr named in a string: {ast.unparse(parents[node])}')
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call) and ast.unparse(node.func) == 'setattr']
    if len(calls) != 1:
        problems.append(f'{len(calls)} setattr calls; only the boundary loop may call it once')
    for call in calls:
        loop = parents.get(call)
        while loop is not None and not isinstance(loop, ast.For):
            loop = parents.get(loop)
        function = loop
        while function is not None and not isinstance(function, ast.FunctionDef):
            function = parents.get(function)
        ok = (loop is not None and ast.unparse(loop.iter) == 'UNAUDITED' and function is not None and function.name == 'install_boundary'
              and isinstance(loop.target, ast.Tuple) and len(loop.target.elts) == 3 and len(call.args) == 3)
        if ok:
            module_name, attribute = (element.id for element in loop.target.elts[:2])
            imported = {ast.unparse(node.targets[0]) for node in ast.walk(loop) if isinstance(node, ast.Assign)
                        and ast.unparse(node.value) == f'importlib.import_module({module_name})'}
            ok = ast.unparse(call.args[0]) in imported and ast.unparse(call.args[1]) == attribute
        if not ok:
            problems.append(f'setattr outside the UNAUDITED loop of install_boundary: {ast.unparse(call)}')
    declared = [ast.literal_eval(node.value) for node in tree.body if isinstance(node, ast.Assign)
                and [ast.unparse(target) for target in node.targets] == ['UNAUDITED']]
    if declared != [UNAUDITED]:
        problems.append(f'UNAUDITED is {declared}, not the three standard-library launchers')
    if {name for name, _, _ in UNAUDITED} & {path.stem for path in SOURCE.glob('*.py')}:
        problems.append('UNAUDITED names a bridge module')
    return problems

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
        source = (ROOT / 'scripts/demo.py').read_text(encoding='utf-8')
        self.assertEqual(rebinding_problems(source), [], 'the demo must not rebind module attributes')

    def test_the_rebinding_guard_rejects_each_way_around_it(self):
        # The three changes from review round 2 of #195, each of which the earlier guard accepted.
        source = (ROOT / 'scripts/demo.py').read_text(encoding='utf-8')
        loop = 'for module_name, attribute, kind in UNAUDITED:'
        helper = 'def registered(directory):'
        self.assertEqual((source.count(loop), source.count(helper)), (1, 1))
        mutations = {
            'module-level setattr': source + "\nsetattr(wall_server, 'ensure_geometry', lambda *a, **k: True)\n",
            'extended loop': source.replace(loop, "for module_name, attribute, kind in UNAUDITED + (('transport', 'light_request', 'light-request'),):"),
            '__dict__ assignment': source.replace(helper, "def rebind():\n    transport.__dict__['light_request'] = None\n\n\n" + helper),
        }
        # The ordinary spellings from review round 3 of #195 (#196), each of which the round 2 guard accepted.
        def before_helper(body):
            return source.replace(helper, 'def rebind():\n    ' + body.replace('\n', '\n    ') + '\n\n\n' + helper)
        mutations.update({
            'class attribute through a module': before_helper('wall_server.App.state = lambda self, device=None: {}'),
            'import_module root': before_helper("importlib.import_module('wall_server').ensure_geometry = None"),
            'sys.modules root': before_helper("sys.modules['wall_server'].ensure_geometry = None"),
            'module alias': before_helper('module = wall_server\nmodule.ensure_geometry = None'),
            'class alias': before_helper('app = wall_server.App\napp.state = None'),
            'alias of an alias': before_helper('first = wall_server\nsecond = first\nsecond.ensure_geometry = None'),
            'deleted module attribute': before_helper('del wall_server.ensure_geometry'),
            'tuple target': before_helper('wall_server.ensure_geometry, other = None, None'),
            'setattr bound to another name': before_helper("assign = setattr\nassign(wall_server, 'ensure_geometry', None)"),
            'setattr through getattr': before_helper("getattr(__builtins__, 'setattr')(wall_server, 'ensure_geometry', None)"),
            'setattr through builtins': before_helper("import builtins\nbuiltins.setattr(wall_server, 'ensure_geometry', None)"),
            'setattr imported under another name': "from builtins import setattr as assign\n" + source,
        })
        for name, mutated in mutations.items():
            with self.subTest(mutation=name):
                self.assertNotEqual(rebinding_problems(mutated), [])

    def test_tests_inject_device_and_launch_seams(self):
        pattern = re.compile(r"patch\.object\(b,\s*'(light_request|launch_worker|connect_state|load_config)'|\bb\.(light_request|launch_worker|subprocess\.Popen)\s*=")
        for path in sorted((ROOT / 'tests').glob('*.py')):
            with self.subTest(test=path.name):
                self.assertIsNone(pattern.search(path.read_text(encoding='utf-8')))


if __name__ == '__main__':
    unittest.main()
