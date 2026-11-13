import base64
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "skills/ai-action-pi-gongzhonghao/scripts/render.py"
PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jJ2kAAAAASUVORK5CYII=")

class WorkflowTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="wechat-test-")
        self.root = Path(self.temp.name)
        self.inputs = self.root / "中文 inputs"
        self.inputs.mkdir()
        (self.inputs / "素材").mkdir()
        (self.inputs / "素材/a.png").write_bytes(PNG)
        self.article = "# 新作者的新标题\n\n**摘要：** 本期摘要。\n\n正文内容。\n\n![图](image:scene)\n"
        self.config = {"schema_version": 1, "author": "轮值作者乙",
                       "images": [{"id": "scene", "path": "素材/a.png", "kind": "poster",
                                   "use": True, "alt": "示例", "caption": "示例图注。"}]}
        self.save()

    def tearDown(self):
        self.temp.cleanup()

    def save(self):
        (self.inputs / "article.md").write_text(self.article, encoding="utf-8")
        (self.inputs / "issue.json").write_text(json.dumps(self.config, ensure_ascii=False), encoding="utf-8")

    def run_build(self, article=None, config=None, out=None):
        return subprocess.run([sys.executable, str(SCRIPT), "build", "--article", str(article or self.inputs/"article.md"),
                               "--config", str(config or self.inputs/"issue.json"), "--out", str(out or self.root/"成品")],
                              capture_output=True, text=True, cwd=self.root)

    def test_relative_paths_relocate_and_rebuild(self):
        r = self.run_build()
        self.assertEqual(r.returncode, 0, r.stderr)
        moved = self.root / "另一个作者的目录"
        shutil.move(self.root/"成品", moved)
        shutil.move(self.inputs, self.root/"不再使用的原始输入")
        r = self.run_build(moved/"文章.md", moved/"本期配置.json", self.root/"重建")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((self.root/"重建/配图/01_scene.png").read_bytes(), PNG)
        self.assertNotIn(str(self.root), (moved/"本期配置.json").read_text())

    def test_selected_image_cannot_be_omitted(self):
        self.article = self.article.replace("\n\n![图](image:scene)", "")
        self.save()
        r = self.run_build()
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("漏放=scene", r.stderr)
        self.assertFalse((self.root/"成品").exists())

    def test_missing_file_fails_before_output(self):
        self.config["images"][0]["path"] = "missing.jpg"
        self.save()
        r = self.run_build()
        self.assertNotEqual(r.returncode, 0)
        self.assertFalse((self.root/"成品").exists())

    def test_original_image_bytes_and_caption_preserved(self):
        self.assertEqual(self.run_build().returncode, 0)
        self.assertEqual((self.root/"成品/配图/01_scene.png").read_bytes(), PNG)
        self.assertIn("示例图注。", (self.root/"成品/公众号正文.html").read_text())

    def test_existing_output_is_preserved(self):
        self.assertEqual(self.run_build().returncode, 0)
        sentinel = self.root/"成品/保留.txt"
        sentinel.write_text("旧版")
        self.assertNotEqual(self.run_build().returncode, 0)
        self.assertEqual(sentinel.read_text(), "旧版")

    def test_zero_and_seven_images(self):
        for count in [0, 7]:
            self.config["images"] = [{"id": "p"+str(n), "path": "素材/a.png", "kind": "photo",
                                     "use": True, "alt": "图", "caption": "图注"} for n in range(count)]
            self.article = "# 新标题\n\n**摘要：** 摘要。\n\n正文。\n\n" + "\n\n".join("![图](image:p"+str(n)+")" for n in range(count))
            self.save()
            out = self.root/("图数"+str(count))
            r = self.run_build(out=out)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(len(json.loads((out/"配图清单.json").read_text())["images"]), count)

    def test_unused_image_requires_reason(self):
        self.config["images"].append({"id": "unused", "use": False})
        self.save()
        self.assertNotEqual(self.run_build().returncode, 0)
        self.config["images"][-1]["reason"] = "场景重复"
        self.save()
        self.assertEqual(self.run_build().returncode, 0)

    def test_title_mismatch_rejected(self):
        self.config["title_lines"] = ["上一期标题"]
        self.save()
        self.assertNotEqual(self.run_build().returncode, 0)

    def test_readable_draft_has_visible_image_instructions(self):
        self.article += '\n图片之后的正文。\n'
        self.save()
        self.assertEqual(self.run_build().returncode, 0)
        draft = (self.root/'成品/初稿_图片占位.md').read_text()
        self.assertIn('【图片占位 01】', draft)
        self.assertIn('图片内容：示例', draft)
        self.assertIn('对应文件：配图/01_scene.png', draft)
        self.assertIn('图注：示例图注。', draft)
        self.assertNotIn('image:scene', draft)
        self.assertLess(draft.index('正文内容。'), draft.index('【图片占位 01】'))
        self.assertLess(draft.index('【图片占位 01】'), draft.index('图片之后的正文。'))
        html = (self.root/'成品/初稿_图片占位.html').read_text()
        self.assertNotIn('<img ', html)
        self.assertIn('图片占位 01', html)

if __name__ == "__main__":
    unittest.main()
