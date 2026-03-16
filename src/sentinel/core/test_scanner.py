"""
Tests for CodeScanner multi-language support.

Validates Java and TypeScript/TSX import extraction and TypeScript
``any``-type detection added to :class:`~sentinel.core.scanner.CodeScanner`.
"""

import unittest

from sentinel.core.scanner import CodeScanner


class TestCodeScannerPython(unittest.TestCase):
    """Regression tests – ensure existing Python behaviour is unchanged."""

    def setUp(self):
        self.scanner = CodeScanner()

    def test_find_imports_plain_import(self):
        code = "import os\nimport sys\n"
        self.assertEqual(self.scanner.find_imports(code), ["os", "sys"])

    def test_find_imports_from_import(self):
        code = "from pathlib import Path\n"
        self.assertEqual(self.scanner.find_imports(code), ["pathlib"])

    def test_find_imports_default_ext_is_python(self):
        """Calling find_imports without file_ext behaves as Python."""
        code = "import os\n"
        self.assertEqual(self.scanner.find_imports(code), ["os"])

    def test_get_functions_basic(self):
        code = "def foo(x):\n    return x\n"
        funcs = self.scanner.get_functions(code)
        self.assertEqual(len(funcs), 1)
        self.assertEqual(funcs[0]["name"], "foo")


class TestCodeScannerJava(unittest.TestCase):
    def setUp(self):
        self.scanner = CodeScanner()

    def test_find_imports_simple(self):
        code = "import com.example.Foo;\nimport java.util.List;\n"
        imports = self.scanner.find_imports(code, ".java")
        self.assertIn("com.example.Foo", imports)
        self.assertIn("java.util.List", imports)

    def test_find_imports_static(self):
        code = "import static com.example.Bar.method;\n"
        imports = self.scanner.find_imports(code, ".java")
        self.assertIn("com.example.Bar.method", imports)

    def test_find_imports_empty(self):
        code = "public class Foo {}\n"
        self.assertEqual(self.scanner.find_imports(code, ".java"), [])

    def test_find_imports_multiple(self):
        code = (
            "import com.example.UserController;\n"
            "import com.example.OrderService;\n"
        )
        imports = self.scanner.find_imports(code, ".java")
        self.assertEqual(len(imports), 2)
        self.assertIn("com.example.UserController", imports)
        self.assertIn("com.example.OrderService", imports)


class TestCodeScannerTypeScript(unittest.TestCase):
    def setUp(self):
        self.scanner = CodeScanner()

    def test_find_imports_named(self):
        code = 'import { Foo } from "./bar";\n'
        imports = self.scanner.find_imports(code, ".ts")
        self.assertIn("./bar", imports)

    def test_find_imports_default(self):
        code = 'import Bar from "./baz";\n'
        imports = self.scanner.find_imports(code, ".ts")
        self.assertIn("./baz", imports)

    def test_find_imports_namespace(self):
        code = 'import * as Baz from "./qux";\n'
        imports = self.scanner.find_imports(code, ".ts")
        self.assertIn("./qux", imports)

    def test_find_imports_empty(self):
        code = "const x: number = 1;\n"
        self.assertEqual(self.scanner.find_imports(code, ".ts"), [])

    def test_find_imports_tsx(self):
        code = 'import React from "react";\n'
        imports = self.scanner.find_imports(code, ".tsx")
        self.assertIn("react", imports)

    def test_find_any_usages_present(self):
        code = "let x: any = 5;\n"
        usages = self.scanner.find_any_usages(code, ".ts")
        self.assertGreater(len(usages), 0)
        self.assertTrue(all(u == "any" for u in usages))

    def test_find_any_usages_in_parameter(self):
        code = "function test(a: any): void {}\n"
        usages = self.scanner.find_any_usages(code, ".ts")
        self.assertGreater(len(usages), 0)

    def test_find_any_usages_absent(self):
        code = "let x: string = 'hello';\n"
        usages = self.scanner.find_any_usages(code, ".ts")
        self.assertEqual(usages, [])

    def test_find_any_usages_default_ext(self):
        """Calling find_any_usages without file_ext defaults to .ts."""
        code = "let x: any = 1;\n"
        usages = self.scanner.find_any_usages(code)
        self.assertGreater(len(usages), 0)

    def test_find_any_usages_tsx(self):
        code = "const fn = (x: any) => x;\n"
        usages = self.scanner.find_any_usages(code, ".tsx")
        self.assertGreater(len(usages), 0)

    def test_find_any_usages_multiple(self):
        code = "let a: any;\nlet b: any;\n"
        usages = self.scanner.find_any_usages(code, ".ts")
        self.assertEqual(len(usages), 2)


if __name__ == "__main__":
    unittest.main()
