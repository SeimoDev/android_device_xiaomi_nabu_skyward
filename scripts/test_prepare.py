import unittest

from prepare import recovery_header


class RecoveryHeaderTests(unittest.TestCase):
    def header(self, commandline):
        header = bytearray(b"\x5a" * 4096)
        header[44:1580] = commandline.encode().ljust(1536, b"\0")
        return header

    def test_rom_empty_commandline_selects_recovery_bootloader_path(self):
        original = self.header("")
        result = recovery_header(original)
        words = result[44:1580].split(b"\0")[0].decode().split()
        self.assertIn("androidboot.fastboot=1", words)
        self.assertIn("twrpfastboot=1", words)
        self.assertEqual(result[:44], original[:44])
        self.assertEqual(result[1580:], original[1580:])

    def test_preserves_device_arguments_and_replaces_duplicate_flags(self):
        original = self.header("console=ttyMSM0 twrpfastboot=0 twrpfastboot=1 androidboot.fastboot=0 androidboot.fastboot=1 androidboot.selinux=enforcing")
        result = recovery_header(original)
        words = result[44:1580].split(b"\0")[0].decode().split()
        self.assertEqual([w for w in words if w.startswith("androidboot.fastboot=")], ["androidboot.fastboot=1"])
        self.assertEqual([w for w in words if w.startswith("twrpfastboot=")], ["twrpfastboot=1"])
        self.assertIn("console=ttyMSM0", words)
        self.assertIn("androidboot.selinux=permissive", words)
        self.assertEqual(recovery_header(result), result)

    def test_rejects_a_commandline_that_would_damage_the_next_field(self):
        with self.assertRaises(ValueError):
            recovery_header(self.header("x" * 1520))


if __name__ == "__main__":
    unittest.main()
