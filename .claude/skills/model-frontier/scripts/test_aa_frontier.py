import json
import unittest

import aa_frontier


def model(slug, release, effort, level, index, cost, creator="anthropic", price_in=2.0):
    return {
        "id": slug,
        "slug": slug,
        "shortName": f"{release} ({effort})",
        "release": {"slug": release},
        "creator": {"slug": creator},
        "effort": {"slug": effort, "level": level},
        "intelligenceIndex": index,
        "intelligenceIndexCostPerTask": {"cost": {"total": cost, "output": cost / 2}},
        "price1mInputTokens": price_in,
        "price1mOutputTokens": price_in * 5,
        "cacheHitPrice": price_in / 20,
    }


def page(objects, version="5.0.1"):
    payload = json.dumps({"label": f"Artificial Analysis Intelligence Index v{version}", "models": objects})
    half = len(payload) // 2
    chunks = [payload[:half], payload[half:]]
    scripts = "".join(f'<script>self.__next_f.push([1,{json.dumps(c)}])</script>' for c in chunks)
    return f"<html><body>{scripts}</body></html>"


class ParsePageTest(unittest.TestCase):
    def test_reads_every_variant_across_chunks(self):
        html = page([model("s-med", "s", "medium", 30, 30.8, 0.78), model("s-high", "s", "high", 40, 42.1, 1.64)])
        version, models = aa_frontier.parse_page(html)
        self.assertEqual(version, "5.0.1")
        self.assertEqual({m["slug"]: (m["effort"], m["index"], m["cost_per_task"]) for m in models}, {"s-med": ("medium", 30.8, 0.78), "s-high": ("high", 42.1, 1.64)})

    def test_fails_loudly_without_rsc(self):
        with self.assertRaises(aa_frontier.ScrapeError):
            aa_frontier.parse_page("<html></html>")

    def test_fails_loudly_when_fields_renamed(self):
        obj = model("s-med", "s", "medium", 30, 30.8, 0.78)
        obj["aaIndex"] = obj.pop("intelligenceIndex")
        with self.assertRaises(aa_frontier.ScrapeError):
            aa_frontier.parse_page(page([obj]))

    def test_fails_on_two_index_versions(self):
        html = page([model("a", "s", "low", 10, 20, 0.5)]) + page([], version="4.3.2")
        with self.assertRaises(aa_frontier.ScrapeError):
            aa_frontier.parse_page(html)


class FrontierTest(unittest.TestCase):
    def setUp(self):
        _, self.models = aa_frontier.parse_page(page([
            model("s-med", "s", "medium", 30, 31, 0.78),
            model("s-high", "s", "high", 40, 42, 1.64),
            model("s-xhigh", "s", "xhigh", 50, 50, 4.09),
            model("o-high", "o", "high", 40, 52, 3.46, price_in=4.0),
        ]))

    def test_pareto_drops_dominated(self):
        self.assertEqual(aa_frontier.pareto(self.models), {"s-med", "s-high", "o-high"})

    def test_role_moves_hide_dominated_and_report_ratios(self):
        roles = {"review": {"release": "s", "effort": "medium"}, "coder": {"release": "s", "effort": "medium"}}
        text = "\n".join(aa_frontier.role_rows(self.models, roles))
        self.assertIn("### review, coder: now", text)
        self.assertIn("| s (high) | 42 | +11 | 2.1x | 1.0x |", text)
        self.assertIn("| o (high) | 52 | +21 | 4.4x | 2.0x |", text)
        self.assertNotIn("s (xhigh)", text)
        self.assertIn("1 dominated move(s) hidden", text)

    def test_svg_marks_roles_sharing_a_point_once(self):
        roles = {"review": {"release": "s", "effort": "medium"}, "coder": {"release": "s", "effort": "medium"}}
        svg = aa_frontier.render_svg(self.models, roles, "5.0.1", "2026-11-19")
        self.assertTrue(svg.startswith("<svg"))
        self.assertIn(">review, coder</text>", svg)
        self.assertEqual(svg.count('r="9"'), 1)


if __name__ == "__main__":
    unittest.main()
