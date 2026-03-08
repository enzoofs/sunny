"""Tests for provider.decrypt internal crypto functions."""

import unittest
from provider.decrypt import (
    _hash_key,
    _seed_shift,
    _columnar_decrypt,
    _seed_shuffle,
    _substitution_decrypt,
    _megacloud_keygen,
)


class TestHashKey(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(_hash_key(""), 0)

    def test_deterministic(self):
        h1 = _hash_key("test_key_123")
        h2 = _hash_key("test_key_123")
        self.assertEqual(h1, h2)

    def test_different_keys(self):
        self.assertNotEqual(_hash_key("abc"), _hash_key("xyz"))

    def test_32bit_bound(self):
        h = _hash_key("a" * 1000)
        self.assertLessEqual(h, 0xFFFFFFFF)


class TestSeedShuffle(unittest.TestCase):
    def test_same_key_same_result(self):
        arr = list("abcdefghij")
        s1 = _seed_shuffle(arr, "key1")
        s2 = _seed_shuffle(arr, "key1")
        self.assertEqual(s1, s2)

    def test_different_key_different_result(self):
        arr = list("abcdefghij")
        s1 = _seed_shuffle(arr, "key1")
        s2 = _seed_shuffle(arr, "key2")
        self.assertNotEqual(s1, s2)

    def test_preserves_elements(self):
        arr = list("abcdefghij")
        shuffled = _seed_shuffle(arr, "some_key")
        self.assertEqual(sorted(shuffled), sorted(arr))


class TestSeedShift(unittest.TestCase):
    def test_roundtrip_not_identity(self):
        """Shifting with a key should change the text."""
        char_array = [chr(32 + i) for i in range(95)]
        original = "Hello World 123"
        shifted = _seed_shift(original, "mykey", char_array)
        self.assertNotEqual(original, shifted)

    def test_chars_outside_array_unchanged(self):
        """Characters outside the printable ASCII range should pass through."""
        char_array = [chr(32 + i) for i in range(95)]
        # \x01 is outside printable range
        result = _seed_shift("\x01\x02\x03", "key", char_array)
        self.assertEqual(result, "\x01\x02\x03")


class TestColumnarDecrypt(unittest.TestCase):
    def test_short_string(self):
        """Columnar decrypt should return all chars."""
        result = _columnar_decrypt("abc", "xy")
        self.assertEqual(len(result), 3)

    def test_deterministic(self):
        r1 = _columnar_decrypt("hello world", "key123")
        r2 = _columnar_decrypt("hello world", "key123")
        self.assertEqual(r1, r2)


class TestSubstitutionDecrypt(unittest.TestCase):
    def test_deterministic(self):
        char_array = [chr(32 + i) for i in range(95)]
        r1 = _substitution_decrypt("Test!", "key", char_array)
        r2 = _substitution_decrypt("Test!", "key", char_array)
        self.assertEqual(r1, r2)

    def test_preserves_length(self):
        char_array = [chr(32 + i) for i in range(95)]
        src = "Hello World!!"
        result = _substitution_decrypt(src, "somekey", char_array)
        self.assertEqual(len(result), len(src))


class TestMegacloudKeygen(unittest.TestCase):
    def test_deterministic(self):
        k1 = _megacloud_keygen("mega_key", "client_key")
        k2 = _megacloud_keygen("mega_key", "client_key")
        self.assertEqual(k1, k2)

    def test_output_printable(self):
        key = _megacloud_keygen("testmega", "testclient")
        for ch in key:
            self.assertGreaterEqual(ord(ch), 32)
            self.assertLessEqual(ord(ch), 126)

    def test_different_inputs(self):
        k1 = _megacloud_keygen("key_a", "client_a")
        k2 = _megacloud_keygen("key_b", "client_b")
        self.assertNotEqual(k1, k2)


if __name__ == "__main__":
    unittest.main()
