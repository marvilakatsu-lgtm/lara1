from pathlib import Path
import ast
import unittest


ROOT = Path(__file__).resolve().parents[1]


class CatalogoAttachmentRegressionTests(unittest.TestCase):
    def test_catalogo_render_omits_missing_file_in_send_message_calls(self):
        source_path = ROOT / "cogs" / "catalogo.py"
        source = source_path.read_text(encoding="utf-8")
        tree = ast.parse(source)

        # A send_kwargs helper already conditionally adds `file`; callbacks that
        # receive optional (embed, file) render results must use that helper.
        self.assertIn('return dict(embed=emb, view=view, **({"file": file} if file else {}))', source)
        self.assertGreaterEqual(source.count('ephemeral=True, **send_kwargs(emb, file, v)'), 2)

        unguarded = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if not (isinstance(func, ast.Attribute) and func.attr == "send_message"):
                continue
            if any(keyword.arg == "file" and isinstance(keyword.value, ast.Name) and keyword.value.id == "file" for keyword in node.keywords):
                unguarded.append(node.lineno)
        self.assertEqual(unguarded, [], f"send_message passa file=None diretamente nas linhas: {unguarded}")


if __name__ == "__main__":
    unittest.main()
