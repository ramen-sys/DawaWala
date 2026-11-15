import unittest

from dawawala_risk.readability import (
    count_sentences, count_syllables, flesch_kincaid_grade)


class ReadabilityTests(unittest.TestCase):
    def test_syllables(self):
        for word, n in (("cat", 1), ("medicine", 3), ("table", 2),
                        ("make", 1), ("the", 1), ("pharmacist", 3),
                        ("123", 1), ("", 1)):
            self.assertEqual(count_syllables(word), n, word)

    def test_sentences(self):
        self.assertEqual(count_sentences("One. Two! Three?"), 3)
        self.assertEqual(count_sentences("Version v1.2.0 is here."), 1)
        self.assertEqual(count_sentences(""), 1)

    def test_grade_simple_vs_complex(self):
        easy = "The cat sat on the mat. It was a big cat."
        hard = ("Pharmacokinetic interactions notwithstanding, "
                "contraindicated concomitant administration necessitates "
                "comprehensive therapeutic reevaluation.")
        self.assertLess(flesch_kincaid_grade(easy), 3)
        self.assertGreater(flesch_kincaid_grade(hard), 15)

    def test_no_words(self):
        self.assertEqual(flesch_kincaid_grade("123 ..."), 0.0)


if __name__ == "__main__":
    unittest.main()
