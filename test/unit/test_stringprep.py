import unittest

from nbxmpp.stringprep import check_bidi
from nbxmpp.stringprep import nameprep
from nbxmpp.stringprep import nodeprep
from nbxmpp.stringprep import resourceprep
from nbxmpp.stringprep import saslprep


class TestBidi(unittest.TestCase):
    def test_empty_string(self):
        check_bidi("")

    def test_L_RAL_violation(self):
        with self.assertRaises(ValueError):
            check_bidi("\u05be\u0041")


class TestNodeprep(unittest.TestCase):
    def test_map_to_nothing(self):
        self.assertEqual(
            "ix",
            nodeprep("I\u00adX"),
            "Nodeprep requirement: map SOFT HYPHEN to nothing",
        )

    def test_case_fold(self):
        self.assertEqual(
            "ssa", nodeprep("ßA"), "Nodeprep requirement: map ß to ss, A to a"
        )

    def test_nfkc(self):
        self.assertEqual("a", nodeprep("\u00aa"), "Nodeprep requirement: NFKC")
        self.assertEqual("ix", nodeprep("\u2168"), "Nodeprep requirement: NFKC")

    def test_prohibited_character(self):
        with self.assertRaisesRegex(
            ValueError,
            r"U\+0007",
            msg="Nodeprep requirement: prohibited character (C.2.1)",
        ):
            nodeprep("\u0007")

        with self.assertRaisesRegex(
            ValueError,
            r"U\+200e",
            msg="Nodeprep requirement: prohibited character (C.8)",
        ):
            nodeprep("\u200e")

        with self.assertRaisesRegex(
            ValueError,
            r"U\+003e",
            msg="Nodeprep requirement: prohibited character (custom)",
        ):
            nodeprep(">")

    def test_unassigned(self):
        with self.assertRaises(ValueError, msg="Nodeprep requirement: unassigned"):
            nodeprep("\u0221", allow_unassigned=False)

        with self.assertRaises(ValueError, msg="enforce no unassigned by default"):
            nodeprep("\u0221")

        self.assertEqual("\u0221", nodeprep("\u0221", allow_unassigned=True))


class TestNameprep(unittest.TestCase):
    def test_map_to_nothing(self):
        self.assertEqual(
            "ix",
            nameprep("I\u00adX"),
            "Nameprep requirement: map SOFT HYPHEN to nothing",
        )

    def test_case_fold(self):
        self.assertEqual(
            "ssa", nameprep("ßA"), "Nameprep requirement: map ß to ss, A to a"
        )

    def test_nfkc(self):
        self.assertEqual("a", nodeprep("\u00aa"), "Nameprep requirement: NFKC")
        self.assertEqual("ix", nodeprep("\u2168"), "Nameprep requirement: NFKC")

    def test_prohibited_character(self):
        with self.assertRaisesRegex(
            ValueError,
            r"U\+06dd",
            msg="Nameprep requirement: prohibited character (C.2.2)",
        ):
            nameprep("\u06dd")

        with self.assertRaisesRegex(
            ValueError,
            r"U\+e000",
            msg="Nameprep requirement: prohibited character (C.3)",
        ):
            nameprep("\ue000")

        with self.assertRaisesRegex(
            ValueError,
            r"U\+1fffe",
            msg="Nameprep requirement: prohibited character (C.4)",
        ):
            nameprep("\U0001fffe")

        with self.assertRaisesRegex(
            ValueError,
            r"U\+d800",
            msg="Nameprep requirement: prohibited character (C.5)",
        ):
            nameprep("\ud800")

        with self.assertRaisesRegex(
            ValueError,
            r"U\+fff9",
            msg="Nameprep requirement: prohibited character (C.6)",
        ):
            nameprep("\ufff9")

        with self.assertRaisesRegex(
            ValueError,
            r"U\+2ff0",
            msg="Nameprep requirement: prohibited character (C.7)",
        ):
            nameprep("\u2ff0")

        with self.assertRaisesRegex(
            ValueError,
            r"U\+e0001",
            msg="Nameprep requirement: prohibited character (C.9)",
        ):
            nameprep("\U000e0001")

    def test_unassigned(self):
        with self.assertRaises(ValueError, msg="Nameprep requirement: unassigned"):
            nameprep("\u0221", allow_unassigned=False)

        with self.assertRaises(ValueError, msg="enforce no unassigned by default"):
            nameprep("\u0221")

        self.assertEqual("\u0221", nameprep("\u0221", allow_unassigned=True))


class TestResourceprep(unittest.TestCase):
    def test_map_to_nothing(self):
        self.assertEqual(
            "IX",
            resourceprep("I\u00adX"),
            "Resourceprep requirement: map SOFT HYPHEN to nothing",
        )

    def test_nfkc(self):
        self.assertEqual("a", resourceprep("\u00aa"), "Resourceprep requirement: NFKC")
        self.assertEqual("IX", resourceprep("\u2168"), "Resourceprep requirement: NFKC")

    def test_prohibited_character(self):
        with self.assertRaisesRegex(
            ValueError,
            r"U\+0007",
            msg="Resourceprep requirement: prohibited character (C.2.1)",
        ):
            resourceprep("\u0007")

        with self.assertRaisesRegex(
            ValueError,
            r"U\+200e",
            msg="Resourceprep requirement: prohibited character (C.8)",
        ):
            resourceprep("\u200e")

    def test_unassigned(self):
        with self.assertRaises(ValueError, msg="Resourceprep requirement: unassigned"):
            resourceprep("\u0221", allow_unassigned=False)

        with self.assertRaises(ValueError, msg="enforce no unassigned by default"):
            resourceprep("\u0221")

        self.assertEqual("\u0221", resourceprep("\u0221", allow_unassigned=True))


class TestSASLprep(unittest.TestCase):
    def test_map_to_nothing(self):
        self.assertEqual(
            "IX",
            saslprep("I\u00adX"),
            "SASLprep requirement: map SOFT HYPHEN to nothing",
        )

    def test_nfkc(self):
        self.assertEqual("a", saslprep("\u00aa"), "SASLprep requirement: NFKC")
        self.assertEqual("IX", saslprep("\u2168"), "SASLprep requirement: NFKC")

    def test_case_fold(self):
        self.assertNotEqual(
            "user", saslprep("USER"), "SASLprep requirement: No CaseFold"
        )

    def test_prohibited_character(self):
        with self.assertRaisesRegex(
            ValueError,
            r"U\+0007",
            msg="SASLprep requirement: prohibited character (C.2.1)",
        ):
            saslprep("\u0007")

    def test_bidi_check(self):
        with self.assertRaises(ValueError, msg="SASLprep requirement: bidi check"):
            saslprep("\u0627\u0031")

    def test_unassigned(self):
        with self.assertRaises(ValueError, msg="SASLprep requirement: unassigned"):
            saslprep("\u0221", allow_unassigned=False)

        with self.assertRaises(ValueError, msg="enforce no unassigned by default"):
            saslprep("\u0221")

        self.assertEqual("\u0221", saslprep("\u0221", allow_unassigned=True))
