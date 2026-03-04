"""
Tests for ArchitecturalGuardian multi-language scanning.

Validates that the guardian correctly scans Java and TypeScript/TSX files
and generates the expected violation messages.
"""

import os
import tempfile
import unittest

from sentinel.core.guardian import ArchitecturalGuardian


class TestGuardianJavaScanning(unittest.TestCase):
    def setUp(self):
        self.guardian = ArchitecturalGuardian()

    def test_java_file_is_included_in_graph(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            java_path = os.path.join(tmpdir, "OrderService.java")
            with open(java_path, "w") as f:
                f.write("import com.example.OrderRepository;\n")
            graph = self.guardian.analyze_structure(tmpdir)
            self.assertIn(java_path, graph)

    def test_java_imports_are_extracted(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            java_path = os.path.join(tmpdir, "OrderService.java")
            with open(java_path, "w") as f:
                f.write("import com.example.UserController;\n")
            graph = self.guardian.analyze_structure(tmpdir)
            imports = graph[java_path]["imports"]
            self.assertIn("com.example.UserController", imports)

    def test_java_violation_message_format(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            java_path = os.path.join(tmpdir, "OrderService.java")
            with open(java_path, "w") as f:
                f.write("import com.example.UserController;\n")
            graph = self.guardian.analyze_structure(tmpdir)
            # Full FQ import path is preserved in the graph
            self.assertIn("com.example.UserController", graph[java_path]["imports"])
            violations = self.guardian.check_rules([])
            self.assertTrue(
                any(
                    "Import of 'UserController' in 'OrderService.java'" in v
                    for v in violations
                )
            )

    def test_java_static_import_uses_class_name(self):
        """Static import 'com.example.Bar.method' should yield 'Bar', not 'method'."""
        with tempfile.TemporaryDirectory() as tmpdir:
            java_path = os.path.join(tmpdir, "OrderService.java")
            with open(java_path, "w") as f:
                f.write("import static com.example.UserController.getInstance;\n")
            self.guardian.analyze_structure(tmpdir)
            violations = self.guardian.check_rules([])
            self.assertTrue(
                any("Import of 'UserController'" in v for v in violations)
            )
            self.assertFalse(
                any("Import of 'getInstance'" in v for v in violations)
            )

    def test_java_no_imports_no_violations(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            java_path = os.path.join(tmpdir, "Foo.java")
            with open(java_path, "w") as f:
                # Include Javadoc so the new [JAVADOC] rule does not trigger.
                f.write("/** A well-documented class. */\npublic class Foo {}\n")
            self.guardian.analyze_structure(tmpdir)
            violations = self.guardian.check_rules([])
            self.assertEqual(violations, [])


class TestGuardianTypeScriptScanning(unittest.TestCase):
    def setUp(self):
        self.guardian = ArchitecturalGuardian()

    def test_ts_file_is_included_in_graph(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ts_path = os.path.join(tmpdir, "index.ts")
            with open(ts_path, "w") as f:
                f.write('import { Foo } from "./foo";\n')
            graph = self.guardian.analyze_structure(tmpdir)
            self.assertIn(ts_path, graph)

    def test_tsx_file_is_included_in_graph(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tsx_path = os.path.join(tmpdir, "App.tsx")
            with open(tsx_path, "w") as f:
                f.write('import React from "react";\n')
            graph = self.guardian.analyze_structure(tmpdir)
            self.assertIn(tsx_path, graph)

    def test_ts_imports_are_extracted(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ts_path = os.path.join(tmpdir, "index.ts")
            with open(ts_path, "w") as f:
                f.write('import { Foo } from "./foo";\n')
            graph = self.guardian.analyze_structure(tmpdir)
            self.assertIn("./foo", graph[ts_path]["imports"])

    def test_ts_any_usage_produces_violation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ts_path = os.path.join(tmpdir, "index.ts")
            with open(ts_path, "w") as f:
                f.write("let x: any = 5;\n")
            self.guardian.analyze_structure(tmpdir)
            violations = self.guardian.check_rules([])
            self.assertTrue(
                any("Found usage of 'any'" in v for v in violations)
            )

    def test_ts_no_any_usage_no_violation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ts_path = os.path.join(tmpdir, "index.ts")
            with open(ts_path, "w") as f:
                f.write("let x: string = 'hello';\n")
            self.guardian.analyze_structure(tmpdir)
            violations = self.guardian.check_rules([])
            self.assertEqual(violations, [])

    def test_tsx_any_usage_produces_violation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tsx_path = os.path.join(tmpdir, "App.tsx")
            with open(tsx_path, "w") as f:
                f.write("const fn = (x: any) => x;\n")
            self.guardian.analyze_structure(tmpdir)
            violations = self.guardian.check_rules([])
            self.assertTrue(
                any("Found usage of 'any'" in v for v in violations)
            )


class TestGuardianMixedScanning(unittest.TestCase):
    def setUp(self):
        self.guardian = ArchitecturalGuardian()

    def test_py_java_ts_all_scanned(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            py_path = os.path.join(tmpdir, "module.py")
            java_path = os.path.join(tmpdir, "Service.java")
            ts_path = os.path.join(tmpdir, "index.ts")
            with open(py_path, "w") as f:
                f.write("import os\n")
            with open(java_path, "w") as f:
                f.write("import com.example.Repo;\n")
            with open(ts_path, "w") as f:
                f.write('import { X } from "./x";\n')
            graph = self.guardian.analyze_structure(tmpdir)
            self.assertIn(py_path, graph)
            self.assertIn(java_path, graph)
            self.assertIn(ts_path, graph)

    def test_unsupported_extension_not_scanned(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            txt_path = os.path.join(tmpdir, "notes.txt")
            with open(txt_path, "w") as f:
                f.write("some text\n")
            graph = self.guardian.analyze_structure(tmpdir)
            self.assertNotIn(txt_path, graph)


if __name__ == "__main__":
    unittest.main()
