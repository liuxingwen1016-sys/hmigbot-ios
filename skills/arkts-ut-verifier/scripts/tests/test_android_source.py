import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPTS = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location("android_source", SCRIPTS / "android_source.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class EnumTest(unittest.TestCase):
    def test_kotlin_last_entry_without_comma_and_one_line(self):
        for source in ("enum class Color {\n RED,\n GREEN,\n BLUE\n}", "enum class Color { RED, GREEN, BLUE; }"):
            self.assertEqual(module.enum_members(source, "Color"), ["RED", "GREEN", "BLUE"])

    def test_java_and_nonuppercase_members(self):
        self.assertEqual(module.enum_members("public enum Color { Red, Green, Blue }", "Color"), ["Red", "Green", "Blue"])

    def test_nested_arguments_entry_bodies_annotations_and_comments(self):
        source = '''enum class Color(val label: String) {
          @Label("not,an;entry") RED(call(1, listOf(2, 3))) { override fun x() { println("}; fake") } },
          /* outer /* nested */ comment */ GREEN("text"), BLUE("""{}; comma,"""),
          ; fun method() = Other.VALUE
        }
        enum class Other { VALUE }
        '''
        self.assertEqual(module.enum_members(source, "Color"), ["RED", "GREEN", "BLUE"])

    def test_sealed_is_not_misreported_as_complete(self):
        source = "sealed interface State\ndata object Ready : State\ndata class Failed(val reason: String) : State\nclass Unrelated\n"
        with self.assertRaisesRegex(ValueError, "cannot prove"):
            module.enum_members(source, "State")

    def test_unsupported_or_truncated_syntax_never_returns_partial_set(self):
        for source in ("enum class Color { RED, GREEN", "enum class Color { RED, `odd name` }",
                       "enum class Color { RED val other = 2 }", "enum class Color { RED, /* unterminated"):
            with self.subTest(source=source), self.assertRaises(ValueError):
                module.enum_members(source, "Color")

    def test_multiple_declarations_are_ambiguous(self):
        with self.assertRaisesRegex(ValueError, "found 2"):
            module.enum_members("class A { enum Color { RED } } class B { enum Color { BLUE } }", "Color")

    def test_empty_enum_is_a_proven_empty_set(self):
        self.assertEqual(module.enum_members("enum class Color { ; fun x() = 1 }", "Color"), [])


class SourceSearchTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="oracle with spaces ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def add(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def run_command(self, command, *args):
        return subprocess.run(["bash", str(SCRIPTS / "android-oracle.sh"), command, str(self.root), *args], text=True, capture_output=True)

    def test_java_method_and_enum_definitions(self):
        self.add("app/src/main/java/Color.java", "public enum Color { RED, BLUE; public static Color fromCode(int value) { return RED; } }")
        for symbol, kind in (("fromCode", "fun"), ("Color", "enum")):
            result = self.run_command("find-sym", symbol, kind)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Color.java", result.stdout)

    def test_kotlin_extension_and_generic_functions(self):
        self.add("lib/src/commonMain/kotlin/Helpers.kt", "fun <T> List<T>.choose(value: T): T = value\nfun String.trimmed(): String = this.trim()")
        for name in ("choose", "trimmed"):
            result = self.run_command("find-sym", name, "fun")
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_calls_and_comments_are_not_definitions(self):
        self.add("app/src/main/java/Client.java", "class Client { void run() { fromCode(1); return fromCode(2); } // public Color fromCode(int x)\n }")
        result = self.run_command("find-sym", "fromCode", "fun")
        self.assertEqual(result.returncode, 2, result.stdout)

    def test_test_search_uses_content_java_and_source_sets(self):
        paths = ["app/src/test/java/CodecChecks.java", "app/src/androidTest/kotlin/Scenario.kt", "lib/src/commonTest/kotlin/Example.kt", "app/src/testDebug/java/DebugChecks.java"]
        for name in paths:
            self.add(name, "// verifies fromCode")
        self.add("app/src/main/java/Codec.java", "// fromCode")
        result = self.run_command("tests", "fromCode")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("count=4", result.stdout)
        self.assertNotIn("Codec.java", result.stdout)

    def test_keywords_include_java_and_exclude_tests_build_generated_vendor(self):
        self.add("app/src/debug/java/Codec.java", "class Codec { /* needle */ }")
        for name in ("app/build/src/main/Noise.kt", "app/src/main/generated/Noise.java", "vendor/src/main/Noise.kt", "app/src/test/kotlin/Noise.kt"):
            self.add(name, "needle")
        result = self.run_command("grep-kw", "needle")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Codec.java", result.stdout)
        self.assertNotIn("Noise", result.stdout)

    def test_enum_wrapper_propagates_unsupported_exit(self):
        path = self.add("State.kt", "sealed interface State\nclass Unrelated")
        result = subprocess.run(["bash", str(SCRIPTS / "android-oracle.sh"), "enum", str(path), "State"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertTrue(result.stdout.startswith("UNSUPPORTED\tState\t"))
