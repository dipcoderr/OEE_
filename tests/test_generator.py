import os
import tempfile
import unittest

from generator import generate_dataset


class GeneratorsTest(unittest.TestCase):
    def test_small_scale_dataset_has_expected_tables(self):
        dataset = generate_dataset(seed=20261022, scale=0.01, output_dir=None)

        self.assertIn("plants", dataset)
        self.assertIn("lines", dataset)
        self.assertIn("machines", dataset)
        self.assertIn("shifts", dataset)
        self.assertIn("products", dataset)
        self.assertIn("production_orders", dataset)
        self.assertIn("state_events", dataset)
        self.assertIn("production_counts", dataset)
        self.assertIn("quality_inspections", dataset)
        self.assertIn("oee_aggregate", dataset)

        self.assertGreater(len(dataset["plants"]), 0)
        self.assertGreater(len(dataset["machines"]), 0)
        self.assertGreater(len(dataset["state_events"]), 0)

    def test_oee_components_reconcile(self):
        dataset = generate_dataset(seed=20261022, scale=0.01, output_dir=None)

        for row in dataset["oee_aggregate"]:
            calc = row["availability"] * row["performance"] * row["quality"]
            self.assertAlmostEqual(calc, row["oee"], places=6)

    def test_ground_truth_is_exported_separately(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            dataset = generate_dataset(seed=20261022, scale=0.01, output_dir=tmpdir)
            self.assertIn("ground_truth", dataset)
            self.assertTrue(os.path.exists(os.path.join(tmpdir, "json", "ground_truth.json")))
            self.assertTrue(os.path.exists(os.path.join(tmpdir, "csv", "ground_truth.csv")))
            self.assertTrue(len(dataset["ground_truth"]) >= 1)


if __name__ == "__main__":
    unittest.main()
